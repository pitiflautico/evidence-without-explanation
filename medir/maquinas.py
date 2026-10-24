"""Medición del laboratorio B y cliente simulado (sin API) (notas/diseno-simulador-b.md §3–§5).

- Competencia: puntuación en escenarios retenidos y problemas cumplidos (puntuación ≥ UMBRAL), por fase, rama y
  estrato.
- Diferencias emparejadas: en el trasplante, la unidad es la secuencia (cada una da un almacén), así que el intervalo
  remuestrea secuencias, no problemas.
- Uso de lo heredado (dueño 22/10): si la instancia nueva importa o ejecuta ficheros del almacén
  (abrirlos para leerlos se cuenta aparte, como «abren»), en qué clase de problema y con qué resultado.
- Origen de cada artefacto del almacén de LIBRE (descriptivo, nunca exigido): tras un fallo, combinando otros
  artefactos o sin fallo previo.

python -m medir.maquinas <resultados>          informe
python -m medir.maquinas coste <banco> [ramas] [brazos]   coste con el cliente simulado
"""
import json
import random
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from statistics import mean
from types import SimpleNamespace as NS

from generadores import maquinas as G

UMBRAL = G.UMBRAL_IDEAL


def cumplido(f):
    return f['puntuacion'] >= UMBRAL


def emparejada(filas, a, b, campo=cumplido, muestras=4000, semilla=0):
    """Media de (a − b) emparejando por problema, con un intervalo del 90 % que remuestrea secuencias."""
    return contraste(filas, {a: 1, b: -1}, campo, muestras, semilla)


def contraste(filas, pesos, campo=cumplido, muestras=4000, semilla=0):
    """Media por problema de Σ peso·valor de cada rama (solo problemas con todas las ramas), con intervalo del 90 %
    que remuestrea secuencias. Sirve para los efectos del factorial (dueño 23/10)."""
    por = defaultdict(lambda: defaultdict(dict))
    for f in filas:
        por[f['secuencia']][f['problema']][f['rama']] = float(campo(f))
    grupos = [[sum(w * v[r] for r, w in pesos.items()) for v in probs.values() if all(r in v for r in pesos)]
              for probs in por.values()]
    grupos = [g for g in grupos if g]
    if not grupos:
        return None
    todos = [x for g in grupos for x in g]
    rng = random.Random(semilla)
    medias = []
    for _ in range(muestras):
        m = [x for _ in grupos for x in rng.choice(grupos)]
        medias.append(mean(m))
    medias.sort()
    return mean(todos), medias[int(.05 * muestras)], medias[int(.95 * muestras) - 1], len(todos), len(grupos)


def _importados_estaticos(codigo, nombres):
    """Para registros anteriores a `importados` (piloto 22/10): ficheros que el código importa o ejecuta, por texto."""
    salida = set()
    for n in nombres:
        raiz = re.escape(Path(n).stem)
        if re.search(rf'^\s*(from\s+{raiz}\s+import|import\s+(\w+\s*,\s*)*{raiz}\b)', codigo or '', re.M) or \
                re.search(rf'(run_path|exec|exec_module|spec_from_file_location)\([^)]*{re.escape(n)}', codigo or ''):
            salida.add(n)
    return salida


def usos(f, solo_heredados=True, funcional=False, solo_controlador=False):
    """Ficheros del almacén que la instancia usó (en sus ejecuciones o en su controlador). Por defecto, solo los
    heredados: los que ya estaban en el almacén al empezar (no lo que escribió ella misma).
    - funcional=False: abiertos de cualquier modo, también para leerlos (cuenta mirar un fichero como usarlo);
    - funcional=True: importados o ejecutados como código (corrección tras el piloto 22/10);
    - solo_controlador=True (con funcional): solo lo que importa el controlador entregado."""
    if funcional:
        candidatos = {r[len('almacen/'):] for r in {**f.get('inicial', {}), **f.get('final', {})}
                      if r.startswith('almacen/')}
        todos = set()
        for e in [] if solo_controlador else f.get('ejecuciones', []):
            todos |= set(e['importados']) if 'importados' in e else _importados_estaticos(e['codigo'], candidatos)
        todos |= set(f['importados'] or []) if 'importados' in f else \
            _importados_estaticos(f.get('codigo_entregado'), candidatos)
    else:
        todos = {u for e in f.get('ejecuciones', []) for u in e.get('usos', [])} | set(f.get('usos') or [])
    heredados = {r[len('almacen/'):] for r in f.get('inicial', {}) if r.startswith('almacen/')}
    return sorted(todos & heredados if solo_heredados else todos)


def origen_artefactos(filas_libre, almacen_final):
    """Para cada fichero del almacén final de LIBRE: en qué problema y ejecución se escribió por primera vez, y qué lo
    precede (etiqueta descriptiva)."""
    almacen_final = Path(almacen_final)
    modulos = {p.stem for p in almacen_final.rglob('*.py')}
    salida = {}
    previo_fallido = False
    for f in sorted(filas_libre, key=lambda x: x['orden']):
        fallos = 0
        for e in f.get('ejecuciones', []):
            for ruta in e.get('escritos', []):
                if ruta in salida or not (almacen_final / ruta).exists():
                    continue
                try:
                    texto = (almacen_final / ruta).read_text()
                except UnicodeDecodeError:
                    texto = ''
                importa = {m for m in modulos if m != Path(ruta).stem and re.search(rf'\b(import|from)\s+{m}\b', texto)}
                if len(importa) >= 2:
                    etiqueta = 'combina'
                elif fallos or previo_fallido:
                    etiqueta = 'tras_fallo'
                else:
                    etiqueta = 'sin_fallo_previo'
                salida[ruta] = {'problema': f['orden'], 'etiqueta': etiqueta, 'importa': sorted(importa)}
            fallos += e.get('codigo_salida') not in (0, None) or 'Traceback' in e.get('salida', '')
        previo_fallido = not cumplido(f)
    return salida


def informe(filas, salida=None):
    r = {'competencia': {}, 'diferencias': {}, 'uso': {}, 'origen': {}, 'coste': {}}
    for fase in ('construccion', 'trasplante'):
        xs = [f for f in filas if f['fase'] == fase]
        for rama in sorted({f['rama'] for f in xs}):
            for estrato in ('TODOS', 'facil', 'dificil'):
                for clase in (('TODAS', 'afines', 'ajenos') if fase == 'trasplante' else ('TODAS',)):
                    ys = [f for f in xs if f['rama'] == rama and estrato in ('TODOS', f['estrato'])
                          and clase in ('TODAS', f.get('clase'))]
                    if ys:
                        r['competencia'][(fase, rama, estrato, clase)] = {
                            'n': len(ys), 'cumplidos': sum(map(cumplido, ys)), 'puntuacion': mean(f['puntuacion'] for f in ys),
                            'incompletos': sum(bool(f.get('incompleto')) for f in ys),
                            'dolares': mean(f['dolares'] for f in ys), 'pasos': mean(f['pasos'] for f in ys),
                            'ejecuciones': mean(len(f.get('ejecuciones', [])) for f in ys)}
    cons = [f for f in filas if f['fase'] == 'construccion']
    tras = [f for f in filas if f['fase'] == 'trasplante']
    for a, b, xs in [('LIBRE', 'FIJO', cons), ('LIBRE', 'LIBRE_SIN_MEMORIA', cons), ('T_TODO', 'T0', tras),
                     ('T_TODO', 'T_NOTAS', tras), ('T_TODO', 'T_CODIGO_TEXTO', tras), ('T_TODO', 'T_REPERTORIO', tras),
                     ('T_NOTAS', 'T0', tras)]:
        for clase in ('TODAS', 'afines', 'ajenos'):
            ys = [f for f in xs if clase in ('TODAS', f.get('clase', 'TODAS'))]
            d = emparejada(ys, a, b)
            if d and (xs is tras or clase == 'TODAS'):
                r['diferencias'][(a, b, clase)] = d
    for brazo in ('T_TODO', 'T_REPERTORIO'):
        for clase in ('afines', 'ajenos'):
            ys = [f for f in tras if f['rama'] == brazo and f.get('clase') == clase]
            if ys:
                con = [f for f in ys if usos(f, funcional=True)]
                sin = [f for f in ys if not usos(f, funcional=True)]
                r['uso'][(brazo, clase)] = {'episodios': len(ys), 'abren_almacen': sum(bool(usos(f)) for f in ys),
                                            'usan_almacen': len(con),
                                            'cumplidos_usando': sum(map(cumplido, con)),
                                            'cumplidos_sin_usar': sum(map(cumplido, sin)),
                                            'controlador_usa_heredado': sum(
                                                bool(usos(f, funcional=True, solo_controlador=True)) for f in ys)}
    fuente = 'RETRO' if any(f['rama'] == 'RETRO' for f in cons) else 'LIBRE'
    r['fuente'] = fuente
    if salida:
        for sec in sorted({f['secuencia'] for f in cons}):
            carpeta = Path(salida) / 'almacenes' / sec / ('' if fuente == 'LIBRE' else fuente)
            final = sorted(carpeta.glob('tras_*'), key=lambda p: int(p.name[5:]))
            libres = [f for f in cons if f['secuencia'] == sec and f['rama'] == fuente]
            if final and libres:
                r['origen'][sec] = origen_artefactos(libres, final[-1])
    retro(r, cons, tras, fuente)
    for fase in ('construccion', 'informe', 'repertorio', 'trasplante'):
        ys = [f for f in filas if f['fase'] == fase]
        if ys:
            r['coste'][fase] = {'episodios': len(ys), 'dolares': sum(f['dolares'] for f in ys),
                                'tokens_in': sum(c['tokens_in'] for f in ys for c in f['llamadas']),
                                'tokens_out': sum(c['tokens_out'] for f in ys for c in f['llamadas'])}
    return r


FACTORIAL = {'retroalimentación': {'RETRO': .5, 'RETRO_SIN_ALMACEN': .5, 'LIBRE': -.5, 'LIBRE_SIN_MEMORIA': -.5},
             'almacén persistente': {'RETRO': .5, 'LIBRE': .5, 'RETRO_SIN_ALMACEN': -.5, 'LIBRE_SIN_MEMORIA': -.5},
             'interacción': {'RETRO': 1, 'RETRO_SIN_ALMACEN': -1, 'LIBRE': -1, 'LIBRE_SIN_MEMORIA': 1}}
MITAD = 5          # «segunda mitad» de la secuencia: problemas 5 a 8, donde puede haber algo acumulado


def reutilizados(filas_fuente):
    """{fichero: problemas posteriores al que lo creó que lo usan funcionalmente} en la construcción de la fuente."""
    salida = {}
    for f in sorted(filas_fuente, key=lambda x: x['orden']):
        for u in usos(f, funcional=True):
            salida.setdefault(u, []).append(f['orden'])
    return salida


def retro(r, cons, tras, fuente):
    """Factorial y criterio de capacidad reutilizable (dueño 23/10). Una capacidad exige, a la vez: código ejecutable
    construido, usado en problemas posteriores distintos, mejora que disminuye al retirarlo (T_TODO − T_SIN_CODIGO) y
    que no se explica por la misma información en texto (T_TODO − T_HISTORIAL y − T_CODIGO_TEXTO)."""
    r['factorial'], r['capacidad'], r['validaciones'] = {}, {}, {}
    if {f['rama'] for f in cons} >= set(FACTORIAL['interacción']):
        for nombre, pesos in FACTORIAL.items():
            for tramo, ys in (('todos', cons), ('problemas 5–8', [f for f in cons if f['orden'] >= MITAD])):
                d = contraste(ys, pesos)
                if d:
                    r['factorial'][(nombre, tramo)] = d
    for rama in sorted({f['rama'] for f in cons + tras}):
        ys = [f for f in cons + tras if f['rama'] == rama]
        if any('validaciones' in f for f in ys):
            r['validaciones'][rama] = mean(len(f.get('validaciones') or []) for f in ys)
    for sec in sorted({f['secuencia'] for f in cons}):
        reuso = reutilizados([f for f in cons if f['secuencia'] == sec and f['rama'] == fuente])
        t_todo = [f for f in tras if f['secuencia'] == sec and f['rama'] == 'T_TODO']
        r['capacidad'][sec] = {'usados_despues': reuso,
                               'en_2_o_mas_problemas': sorted(u for u, ps in reuso.items() if len(ps) >= 2),
                               'usados_por_T_TODO': sorted({u for f in t_todo for u in usos(f, funcional=True)})}
    for a, b in (('T_TODO', 'T_SIN_CODIGO'), ('T_TODO', 'T_HISTORIAL'), ('T_TODO', 'T_CODIGO_TEXTO'), ('T_TODO', 'T0')):
        for clase in ('afines', 'ajenos', 'facil'):
            ys = [f for f in tras if (f.get('estrato') == 'facil' if clase == 'facil' else
                                      f.get('clase') == clase and f.get('estrato') != 'facil')]
            d = emparejada(ys, a, b)
            if d:
                r['diferencias'][(a, b, clase if clase != 'afines' else 'afines difíciles')] = d


def imprimir(r):
    print('Competencia: n | cumplidos | puntuación media | incompletos | $ | pasos | ejecuciones')
    for (fase, rama, estrato, clase), v in r['competencia'].items():
        print(f'  {fase} {rama} [{estrato}, {clase}]: {v["n"]} | {v["cumplidos"]} | {v["puntuacion"]:.2f} | '
              f'{v["incompletos"]} | {v["dolares"]:.3f} | {v["pasos"]:.0f} | {v["ejecuciones"]:.1f}')
    print('\nDiferencias emparejadas de cumplidos (media, intervalo del 90 % remuestreando secuencias, problemas, secuencias):')
    for (a, b, clase), (m, lo, hi, n, s) in r['diferencias'].items():
        print(f'  {a} − {b} [{clase}]: {m:+.2f} [{lo:+.2f}, {hi:+.2f}] ({n}, {s})')
    print('\nUso de lo heredado (solo ficheros que ya estaban en el almacén al empezar; «usan» = importan o ejecutan, '
          '«abren» incluye leer):')
    for k, v in r['uso'].items():
        print(f'  {k}: {v}')
    if r.get('factorial'):
        print('\nFactorial de construcción (cumplidos; media, intervalo del 90 % remuestreando secuencias, problemas, secuencias):')
        for (nombre, tramo), (m, lo, hi, n, s) in r['factorial'].items():
            print(f'  {nombre} [{tramo}]: {m:+.2f} [{lo:+.2f}, {hi:+.2f}] ({n}, {s})')
    if r.get('validaciones'):
        print('\nValidaciones usadas por episodio:', {k: round(v, 2) for k, v in r['validaciones'].items()})
    if r.get('capacidad'):
        print(f'\nCapacidad reutilizable (fuente {r["fuente"]}; además hacen falta T_TODO − T_SIN_CODIGO, − T_HISTORIAL y '
              '− T_CODIGO_TEXTO positivos, arriba):')
        for sec, v in r['capacidad'].items():
            print(f'  {sec}: {v}')
    print(f'\nOrigen de los artefactos de {r.get("fuente", "LIBRE")} (descriptivo):')
    for sec, arts in r['origen'].items():
        print(f'  {sec}: {arts}')
    print('\nCoste por fase:')
    for k, v in r['coste'].items():
        print(f'  {k}: {v}')


# --------------------------------------------------------------------------------------------------- cliente simulado

INSTRUMENTO = '''"""Estimación de ganancias por toques (escrito por el cliente simulado)."""
import json


def estimar(n_toques=1):
    import maquina
    base = maquina.actuar([[0, 0]])[-1]
    g = []
    for a in range(2):
        u = [0, 0]
        u[a] = 1
        g.append([y - b for y, b in zip(maquina.actuar([u])[-1], base)])
        maquina.actuar([[0, 0]])
    json.dump(g, open('ganancia.json', 'w'))
    return g


def accion(g, lecturas, objetivo, previa):
    import numpy as np
    G = np.array(g).T
    sesgo = np.array(lecturas) - G @ np.array(previa)
    u, *_ = np.linalg.lstsq(G, np.array(objetivo) - sesgo, rcond=None)
    return [max(-3.0, min(3.0, float(v))) for v in u]
'''

CONTROLADOR = '''import json
import instrumento
G = json.load(open('ganancia.json'))
OBJETIVO = {objetivo}


def controlar(lecturas, memoria):
    u = instrumento.accion(G, lecturas, OBJETIVO, memoria.get('u', [0, 0]))
    memoria['u'] = u
    return u
'''


class ClienteMaquinas:
    """Trayectorias plausibles para probar el laboratorio B y estimar su coste sin API. Nunca llama a ningún servicio.
    Entrada: lo que de verdad se enviaría (con caché como en la API); salida: `salida` tokens por turno."""

    def __init__(self, salida=600, usar_modelo=True, exploraciones=0):
        self.salida, self.usar_modelo, self.exploraciones = salida, usar_modelo, exploraciones
        self.messages, self.n, self.previo = self, 0, {}

    def _uso(self, kw, salida):
        clave = json.dumps(kw['messages'][0]['content'], default=str)[:400] + kw.get('system', '')[-40:]
        tokens = (len(kw.get('system', '')) + len(json.dumps(kw.get('tools', []))) +
                  len(json.dumps(kw['messages'], default=str))) / 3.0
        leida = min(self.previo.get(clave, 0), tokens)
        self.previo[clave] = tokens
        return NS(input_tokens=0, cache_read_input_tokens=int(leida), cache_creation_input_tokens=int(tokens - leida),
                  output_tokens=salida)

    def _herramienta(self, kw, nombre, entrada):
        self.n += 1
        return NS(content=[NS(type='tool_use', id=f't{self.n}', name=nombre, input=entrada)],
                  usage=self._uso(kw, self.salida), stop_reason='tool_use')

    def create(self, **kw):
        if 'tools' not in kw:                     # llamada desde el código del taller
            return NS(content=[NS(type='text', text='respuesta simulada')], stop_reason='end_turn',
                      usage=NS(input_tokens=int(len(json.dumps(kw['messages'])) / 3), output_tokens=50))
        nombres = {t['name'] for t in kw['tools']}
        primero = kw['messages'][0]['content']
        primero = primero if isinstance(primero, str) else json.dumps(primero, default=str)
        k = sum(1 for m in kw['messages'] if m['role'] == 'assistant')
        if 'escribir_informe' in nombres:
            return self._herramienta(kw, 'escribir_informe', {'texto': 'Conviene estimar las ganancias con toques '
                                                                         'cortos y corregir con la lectura.'})
        if 'terminar' in nombres:
            pasos = [('ejecutar_python', {'codigo': f'open("almacen/utilidades.py", "w").write({INSTRUMENTO!r})'}),
                     ('terminar', {})]
            return self._herramienta(kw, *pasos[min(k, 1)])
        objetivo = json.loads(re.search(r'Objetivo por canal: (\[[^\]]*\])', primero).group(1))
        if 'ejecutar_python' not in nombres:      # FIJO
            pasos = [('actuar', {'secuencia': [[0, 0], [1, 0], [0, 0], [0, 1]]})] * (1 + self.exploraciones)
            pasos += [('entregar', {'codigo': f'def controlar(lecturas, memoria):\n    return [0.0, 0.0]\n'})]
            return self._herramienta(kw, *pasos[min(k, len(pasos) - 1)])
        tiene = 'instrumento.py' in primero.split('Contenido actual de almacen/:')[-1].split('\n')[0]
        pasos = [] if tiene else [('ejecutar_python', {'codigo': f'open("almacen/instrumento.py", "w").write({INSTRUMENTO!r})'})]
        consulta = '\nimport modelo\nmodelo.preguntar("¿qué opinas?", 50)' if self.usar_modelo else ''
        pasos += [('ejecutar_python', {'codigo': 'import maquina\nprint(maquina.actuar([[1, 0]] * 5))'})] * self.exploraciones
        pasos += [('ejecutar_python', {'codigo': 'import instrumento\nprint(instrumento.estimar())' + consulta}),
                  ('ejecutar_python', {'codigo': f'open("controlador.py", "w").write({CONTROLADOR.format(objetivo=objetivo)!r})'})]
        if 'validar' in nombres:                  # con retroalimentación: valida antes de entregar
            pasos += [('validar', {'ruta': 'controlador.py'})] * (1 + (self.exploraciones > 0))
        pasos += [('entregar', {'ruta': 'controlador.py'})]
        return self._herramienta(kw, *pasos[min(k, len(pasos) - 1)])


def estimar_coste(banco, ramas=('FIJO', 'LIBRE', 'LIBRE_SIN_MEMORIA'), brazos=None, por_episodio=0.5, exploraciones=0):
    """Coste con el cliente simulado. Sin razón conocida con el real: en el A el simulado hacía más turnos que el
    modelo; aquí el número de turnos de exploración es el supuesto (austero, típico, intenso)."""
    from base import maquinas_ramas as R
    from ejecutor import maquinas_correr
    brazos = brazos or R.BRAZOS_TRASPLANTE
    with tempfile.TemporaryDirectory() as d:
        _, gastado = maquinas_correr.correr(ClienteMaquinas(exploraciones=exploraciones), banco, list(ramas), list(brazos), por_episodio,
                                            1e9, Path(d))
        filas = [json.loads(l) for l in (Path(d) / 'registro.jsonl').read_text().splitlines()]
    return gastado, informe(filas)['coste'], len(filas)


def main():
    if sys.argv[1] == 'coste':
        banco = json.loads(Path(sys.argv[2]).read_text())
        ramas = sys.argv[3].split(',') if len(sys.argv) > 3 else ('FIJO', 'LIBRE', 'LIBRE_SIN_MEMORIA')
        brazos = sys.argv[4].split(',') if len(sys.argv) > 4 else None
        for nombre, ex in (('austera', 0), ('típica', 10), ('intensa', 25)):
            gastado, coste, n = estimar_coste(banco, ramas, brazos, exploraciones=ex)
            print(f'{nombre} ({ex} turnos de exploración): {n} episodios, {gastado:.2f} $')
            for k, v in coste.items():
                print(f'  {k}: {v}')
        return
    salida = Path(sys.argv[1])
    filas = [json.loads(l) for l in (salida / 'registro.jsonl').read_text().splitlines() if l.strip()]
    imprimir(informe(filas, salida))


if __name__ == '__main__':
    main()
