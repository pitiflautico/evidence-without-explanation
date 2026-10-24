"""Comparación A / A_PISTA / A+ / X (notas/diseno-a-aplus-x.md), fase 0 sin API."""
import json
import sys
from pathlib import Path

import numpy
import pytest
import scipy

from base import maquinas_entorno as E
from ejecutor.agente import Presupuesto
from generadores import maquinas as G

RAIZ = Path(__file__).resolve().parent.parent


def test_el_entorno_del_taller_es_el_declarado_y_el_taller_lo_ve(tmp_path):
    entorno = json.loads((RAIZ / 'bancos' / 'maquinas' / 'congelado.json').read_text())['entorno_taller']
    assert {'python': sys.version.split()[0], 'numpy': numpy.__version__, 'scipy': scipy.__version__} == entorno
    m = E.Mundo(G.construir('t', ['modo']), tmp_path / 'taller', Presupuesto(maximo=0))
    salida = m.ejecutar('import sys, numpy, scipy, scipy.optimize\nprint(sys.version.split()[0], numpy.__version__, '
                        'scipy.__version__)')
    assert salida.split('\n')[0] == f'{entorno["python"]} {entorno["numpy"]} {entorno["scipy"]}'


# --------------------------------------------------------------------------------------------------- contraste

from types import SimpleNamespace as NS

from base import maquinas_hipotesis as H
from base.taller import contraste as C

CATALOGO = G.TIPOS + ('saturación', 'histéresis', 'régimen', 'regimen', 'retardo', 'deriva', 'acumul', 'alias')


def _lineal(x, acciones, k):
    y, salida = [0.0, 0.0], []
    for u in acciones:
        y = [x[0] * y[0] + x[1] * u[0], x[0] * y[1] + x[1] * u[1]]
        salida.append(list(y))
    return salida


def _datos(a=0.8, b=0.5, n=3, T=60, ruido=0.0, semilla=0):
    import random
    rng, datos = random.Random(semilla), []
    for k in range(n):
        acc = [[rng.uniform(-1, 1), rng.uniform(-1, 1)] for _ in range(T)]
        lec = [[v + rng.gauss(0, ruido) for v in fila] for fila in _lineal([a, b], acc, k)]
        datos.append({'fuente': f't{k}', 'acciones': acc, 'lecturas': lec})
    return datos


def test_contrastar_recupera_parametros_y_distingue_lo_que_los_datos_distinguen():
    estatica = (lambda x, acc, k: [[x[0] * u[0], x[0] * u[1]] for u in acc], [1.0])
    r = C.contrastar({'dinamica': (_lineal, [0.5, 1.0]), 'estatica': estatica}, _datos(ruido=0.02), segundos=30)
    assert r['mejor'] == 'dinamica' and r['no_distinguibles_de_la_mejor'] == []
    assert abs(r['hipotesis']['dinamica']['x'][0] - 0.8) < 0.02 and r['hipotesis']['dinamica']['rms'] < 0.03
    # dos parametrizaciones de la misma explicación: los datos no las distinguen
    otra = (lambda x, acc, k: _lineal([x[0], 2 * x[1]], acc, k), [0.5, 0.5])
    r = C.contrastar({'dinamica': (_lineal, [0.5, 1.0]), 'misma': otra}, _datos(ruido=0.02), segundos=30)
    assert r['no_distinguibles_de_la_mejor'] in (['misma'], ['dinamica'])


def test_contrastar_no_cae_con_una_hipotesis_rota_y_respeta_el_tiempo():
    import time
    rota = (lambda x, acc, k: 1 / 0, [1.0])
    lenta = (lambda x, acc, k: time.sleep(0.05) or _lineal(x, acc, k), [0.5, 1.0])
    t0 = time.monotonic()
    r = C.contrastar({'rota': rota, 'lenta': lenta}, _datos(), segundos=2)
    assert time.monotonic() - t0 < 4 and r['incompleto']
    assert 'ZeroDivisionError' in r['hipotesis']['rota']['error'] and r['mejor'] == 'lenta'
    assert 'TIEMPO AGOTADO' in C.informe(r)


def test_contrastar_no_conoce_el_catalogo_ni_propone_hipotesis():
    """Condición del dueño: solo analiza hipótesis del modelo; no menciona ni genera mecanismos."""
    texto = H.CONTRASTE.read_text().lower()
    assert not [t for t in CATALOGO if t in texto]
    assert 'generadores' not in texto and 'import maquina' not in texto
    for t in (H.PISTA, H.MODULO, H.EXPLORACION, H.DESCRIPCION_CONTEXTO, H.SISTEMA_CONTEXTO):
        assert not [c for c in CATALOGO if c in t.lower()], t


def test_cargar_datos_lee_exploracion_por_tramos_y_validaciones(tmp_path):
    (tmp_path / 'exploracion.jsonl').write_text('\n'.join(json.dumps(x) for x in (
        {'reiniciar': False, 'secuencia': [[1, 0]], 'lecturas': [[0.1, 0.2]]},
        {'reiniciar': False, 'secuencia': [[0, 1]], 'lecturas': [[0.3, 0.4]]},
        {'reiniciar': True, 'secuencia': [[1, 1]], 'lecturas': [[0.5, 0.6]]})) + '\n')
    (tmp_path / 'validaciones').mkdir()
    (tmp_path / 'validaciones' / '1.json').write_text(json.dumps([{'escenario': 1, 'pasos': [
        {'t': 0, 'acciones': [0, 0], 'lecturas': [1, 1]}]}]))
    (tmp_path / 'validaciones' / 'controlador_1.py').write_text('x')
    d = C.cargar_datos(carpeta=tmp_path)
    assert [len(x['acciones']) for x in d] == [2, 1, 1] and d[2]['fuente'] == 'validacion 1 escenario 1'


# --------------------------------------------------------------------------------------------------- brazos

CONTROLADOR = 'def controlar(lecturas, memoria):\n    return [0.1, -0.1]\n'
USA_CONTRASTE = ('import contraste\nd = contraste.cargar_datos()\n'
                 'def s(x, acc, k):\n    return [[x[0] * u[0], x[0] * u[1]] for u in acc]\n'
                 'print(contraste.informe(contraste.contrastar({"h": (s, [0.5])}, d, segundos=5)))')


class Guion:
    """Cliente simulado: un guion por papel (principal o contexto). Nunca llama a ningún servicio."""

    def __init__(self):
        self.messages, self.n, self.vistos = self, 0, []

    def _uso(self):
        return NS(input_tokens=100, cache_read_input_tokens=0, cache_creation_input_tokens=0, output_tokens=50)

    def create(self, **kw):
        if 'tools' not in kw:
            return NS(content=[NS(type='text', text='hola')], usage=self._uso(), stop_reason='end_turn')
        self.vistos.append(kw)
        k = sum(1 for m in kw['messages'] if m['role'] == 'assistant')
        nombres = {t['name'] for t in kw['tools']}
        if kw['system'] == H.SISTEMA_CONTEXTO:
            pasos = [('actuar', {'secuencia': [[1, 0]] * 3}), ('responder', {'texto': 'medido'})]
        else:
            pasos = [('actuar', {'secuencia': [[0, 1]] * 4})]
            if 'abrir_contexto' in nombres:
                pasos.append(('abrir_contexto', {'encargo': 'mide la respuesta al primer actuador'}))
            pasos += [('ejecutar_python', {'codigo': USA_CONTRASTE}), ('validar', {'codigo': CONTROLADOR}),
                      ('entregar', {'codigo': CONTROLADOR})]
        self.n += 1
        nombre, entrada = pasos[min(k, len(pasos) - 1)]
        return NS(content=[NS(type='text', text=f'paso {k}'), NS(type='tool_use', id=f't{self.n}', name=nombre, input=entrada)],
                  usage=self._uso(), stop_reason='tool_use')


@pytest.fixture(scope='module')
def corrida_h(tmp_path_factory):
    from ejecutor import hipotesis_correr as HC
    banco = [{'semilla': 'h-1', 'tipos': ['modo']}, {'semilla': 'h-2', 'tipos': ['saturacion']}]
    salida = tmp_path_factory.mktemp('hip')
    cliente = Guion()
    resumen, gastado = HC.correr(cliente, banco, list(H.BRAZOS), 0.5, 1e9, salida)
    filas = [json.loads(l) for l in (salida / 'registro.jsonl').read_text().splitlines()]
    return banco, salida, filas, resumen, cliente


def test_cada_brazo_recibe_solo_lo_suyo(corrida_h):
    _, salida, filas, resumen, cliente = corrida_h
    assert resumen == ['hecha'] and len(filas) == 8
    por = {(f['problema'], f['brazo']): f for f in filas}
    conv = lambda b: json.loads((salida / 'conversaciones' / 'h-1' / f'{b}.json').read_text())
    for b in H.BRAZOS:
        e = conv(b)['enunciado']
        assert H.EXPLORACION in e
        assert (H.PISTA in e) == (b in ('A_PISTA', 'A_MAS')) and (H.MODULO in e) == (b == 'A_MAS')
        assert por[('h-1', b)]['entregado'] and por[('h-1', b)]['validaciones']
    # el módulo solo existe en el taller de A+: en los demás, importarlo falla
    salidas = {b: por[('h-1', b)]['ejecuciones'][0]['salida'] for b in H.BRAZOS}
    assert 'mejor: h' in salidas['A_MAS'] and all('ModuleNotFoundError' in salidas[b] for b in ('A', 'A_PISTA', 'X'))
    # solo X tiene abrir_contexto; las demás herramientas son las mismas
    principal = [kw for kw in cliente.vistos if kw['system'] != H.SISTEMA_CONTEXTO]
    juegos = {frozenset(t['name'] for t in kw['tools']) for kw in principal}
    assert juegos == {frozenset({'actuar', 'leer', 'entregar', 'ejecutar_python', 'validar'}),
                      frozenset({'actuar', 'leer', 'entregar', 'ejecutar_python', 'validar', 'abrir_contexto'})}


def test_x_abre_contextos_que_comparten_maquina_taller_y_presupuesto(corrida_h):
    _, salida, filas, _, _ = corrida_h
    x = next(f for f in filas if f['problema'] == 'h-1' and f['brazo'] == 'X')
    a = next(f for f in filas if f['problema'] == 'h-1' and f['brazo'] == 'A')
    assert x['contextos'][0]['encargo'].startswith('mide') and x['contextos'][0]['respuesta'] == 'medido'
    assert x['pasos'] == a['pasos'] + 3                                   # los pasos del contexto cuentan
    assert {l['rol'] for l in x['llamadas']} == {'X', 'contexto_1'} and x['dolares'] > a['dolares']
    c = json.loads((salida / 'conversaciones' / 'h-1' / 'X.json').read_text())['contextos'][0]
    assert 'Encargo:' in json.dumps(c['conversacion']) and 'Objetivo por canal' in json.dumps(c['conversacion'])
    # la exploración del contexto queda en el mismo exploracion.jsonl
    lineas = (salida / 'talleres' / 'h-1' / 'X' / 'exploracion.jsonl').read_text().splitlines()
    assert len(lineas) == 2


def test_registro_completo_conversacion_cpu_y_reanudacion(corrida_h):
    banco, salida, filas, _, _ = corrida_h
    from ejecutor import hipotesis_correr as HC
    f = next(f for f in filas if f['brazo'] == 'A_MAS')
    assert f['ejecuciones'][0]['cpu'] >= 0 and 'segundos' in f['ejecuciones'][0] and f['cpu_total'] >= f['cpu_codigo']
    assert f['controladores_validados'] and f['acciones'][0]['lecturas']
    c = json.loads((salida / 'conversaciones' / f['problema'] / 'A_MAS.json').read_text())
    assert any(m['role'] == 'assistant' for m in c['conversacion']) and 'conversacion' not in f
    assert [x['brazo'] for x in filas[:4]] == HC.orden(0, H.BRAZOS) and [x['brazo'] for x in filas[4:]] == HC.orden(1, H.BRAZOS)
    resumen, _ = HC.correr(Guion(), banco, list(H.BRAZOS), 0.5, 1e9, salida)
    assert len((salida / 'registro.jsonl').read_text().splitlines()) == 8


def test_parada_automatica_por_tope(tmp_path):
    from ejecutor import hipotesis_correr as HC
    resumen, gastado = HC.correr(Guion(), [{'semilla': 'h-1', 'tipos': ['modo']}], list(H.BRAZOS), 0.5, 0.5, tmp_path)
    assert resumen[0].startswith('PARADA') and len((tmp_path / 'registro.jsonl').read_text().splitlines()) == 1


# --------------------------------------------------------------------------------------------------- familias

def test_firma_funcional_separa_familias_y_no_variantes():
    from medir.familias import familias, firma_codigo
    C0 = [0.5, -0.5]
    integrador = ('def controlar(l, m):\n    u = m.get("u", [0.0, 0.0])\n'
                  '    u = [u[0] + {g} * (0.5 - l[0]), u[1] + {g} * (-0.5 - l[1])]\n    m["u"] = u\n    return u\n')
    proporcional = 'def controlar(l, m):\n    return [0.3 * (0.5 - l[0]), 0.3 * (-0.5 - l[1])]\n'
    recorte = ('def controlar(l, m):\n    c = lambda x: max(-0.6, min(0.6, x))\n    u = m.get("u", [0.0, 0.0])\n'
               '    u = [u[0] + 0.2 * c(0.5 - l[0]), u[1] + 0.2 * c(-0.5 - l[1])]\n    m["u"] = u\n    return u\n')
    ramas = ('def controlar(l, m):\n    g = 0.3 if l[0] < 1.0 else -0.3\n'
             '    return [g * (0.5 - l[0]), 0.3 * (-0.5 - l[1])]\n')
    assert firma_codigo(integrador.format(g=0.2), C0) == {'memoria': True, 'no_lineal': False, 'conmuta': False}
    assert firma_codigo(proporcional, C0) == {'memoria': False, 'no_lineal': False, 'conmuta': False}
    assert firma_codigo(recorte, C0)['no_lineal'] and not firma_codigo(recorte, C0)['conmuta']
    assert firma_codigo(ramas, C0)['conmuta']
    # cambiar parámetros no es otra familia
    assert familias([integrador.format(g=0.2), integrador.format(g=0.05), proporcional], C0)['distintas'] == 2


def test_comparar_grupos_detecta_un_grupo_sin_aliasing_mas_facil():
    """Criterio de §11: d media sin aliasing ≤ con aliasing + 0,15 y ningún problema sin aliasing con d > 0,5."""
    from ejecutor.hipotesis_correr import comparar_grupos
    p = lambda s, tipos, ing, gen: {'semilla': s, 'tipos': tipos, 'ideal': 1.0, 'ingenuo': ing, 'generico': gen}
    con = [p(f'c{i}', ['aliasing', 'modo'], 0.0, 0.1) for i in range(7)]
    _, ok = comparar_grupos(con + [p(f's{i}', ['modo'], 0.0, 0.2) for i in range(3)])
    assert ok
    _, ok = comparar_grupos(con + [p(f's{i}', ['modo'], 0.0, 0.4) for i in range(3)])
    assert not ok                                     # +0,30 de media
    _, ok = comparar_grupos(con + [p('s0', ['modo'], 0.6, 0.0)] + [p(f's{i}', ['modo'], 0.0, 0.0) for i in (1, 2)])
    assert not ok                                     # uno con d > 0,5


def test_la_exportacion_ciega_quita_los_parrafos_de_cada_brazo():
    """§5.1: la conversación exportada no lleva la pista ni el módulo del enunciado (el resto del ciego es parcial)."""
    from medir.hipotesis_piloto import texto_conversacion
    prob = G.construir('ciego-1', ['saturacion'])
    texto = H.enunciado(prob, 'A_MAS', Path('almacen'))
    conv = {'enunciado': texto, 'conversacion': [{'role': 'user', 'content': texto},
                                                 {'role': 'assistant', 'content': [{'type': 'text', 'text': 'Pruebo.'}]}],
            'texto_final': 'fin', 'contextos': []}
    salida = texto_conversacion(conv)
    assert H.PISTA not in salida and H.MODULO not in salida and 'TURNO 1' in salida and 'Pruebo.' in salida


def test_los_cambios_de_rama_de_la_histeresis_se_cuentan_en_la_maquina_verdadera():
    """§13, P2.1: sin acciones no cambia de rama; barriendo los actuadores entre extremos, sí."""
    from medir.histeresis_piloto import _cambios
    prob = G.construir('rama-1', ['histeresis'])
    assert _cambios(G.maquina_exploracion(prob), [[0.0, 0.0]] * 5) == 0
    barrido = ([[3.0, 3.0]] * 20 + [[-3.0, -3.0]] * 20) * 2 + ([[3.0, -3.0]] * 20 + [[-3.0, 3.0]] * 20) * 2
    assert _cambios(G.maquina_exploracion(prob), barrido) >= 2


def test_el_corredor_pasa_el_esfuerzo_al_presupuesto(tmp_path):
    """Control de esfuerzo (§14): el episodio se corre y se registra con el esfuerzo pedido."""
    from ejecutor import hipotesis_correr as HC
    vistos = []
    def episodio(cliente, prob, brazo, taller, pres):
        vistos.append(pres.esfuerzo)
        return {'brazo': brazo, 'controlador': 'c.py', 'enunciado': '', 'conversacion': [], 'texto_final': '',
                'contextos': []}
    banco = [{'semilla': 'esf-1', 'tipos': ['saturacion']}]
    original, HC.H.episodio = HC.H.episodio, episodio
    try:
        HC.correr(None, banco, ['A'], 0.6, 1.0, tmp_path, esfuerzo='high')
    finally:
        HC.H.episodio = original
    assert vistos == ['high']
    assert json.loads((tmp_path / 'registro.jsonl').read_text())['esfuerzo'] == 'high'
