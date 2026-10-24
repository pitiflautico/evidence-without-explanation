"""Auditoría de anclaje sin gasto (notas/diseno-descubrimiento.md §1): ¿A fracasa porque insiste en una explicación
equivocada o porque le falta información?

Para cada episodio con `validar`, se vuelve a correr cada controlador validado, en el taller aislado, en los mismos
escenarios de validación (el simulador es determinista):
- versión verificada: reproduce exactamente las fracciones registradas;
- causa de cada escenario fallido: los mecanismos M tales que, retirándolos de la especificación, el escenario se cumple;
- el controlador entregado, en esos mismos escenarios: si sigue fallando y si sigue siendo por M;
- estructura: cobertura entre el entregado y el que falló (`medir.reutilizacion.cobertura`).
Clases fijadas antes de clasificar: recursos, sin señal, anclaje, revisión insuficiente, indeterminado, recuperado.

python -m medir.anclaje resultados/maq-retro-piloto bancos/maquinas/retro_piloto.json > resultados/.../anclaje.txt
"""
import copy
import json
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

from base import maquinas_entorno as E
from base import maquinas_retro as RT
from ejecutor.agente import Presupuesto
from generadores import maquinas as G
from medir.reutilizacion import UMBRAL, cobertura

CON_VALIDAR = ('RETRO', 'RETRO_SIN_ALMACEN', 'T0', 'T_HISTORIAL', 'T_SIN_CODIGO', 'T_TODO', 'T_CODIGO_TEXTO')
FALLIDA = 5                     # validación fallida: menos de 5 de 6 escenarios cumplidos
RECURSOS = {'validaciones': RT.VALIDACIONES, 'pasos': 20}


def retirar(espec, tipo):
    e = copy.deepcopy(espec)
    if tipo in ('modo', 'saturacion', 'histeresis'):
        e[tipo] = None
    else:
        e[{'retardo': 'retardo', 'acumulador': 'lam', 'aliasing': 'aliasing', 'deriva': 'deriva'}[tipo]] = \
            [{'retardo': 0, 'acumulador': 0.0, 'aliasing': 1, 'deriva': 0.0}[tipo]] * len(e[{'retardo': 'retardo',
             'acumulador': 'lam', 'aliasing': 'aliasing', 'deriva': 'deriva'}[tipo]])
    return e


def fracciones(m, ruta, prob, ks=None):
    """Fracción de la ventana en tolerancia de cada escenario de validación (o de los `ks`), con el controlador aislado."""
    c = m.controlador(ruta)
    try:
        esc = RT.escenarios_validacion(m.prob)
        salida = {k: round(RT.escenario_validacion(prob, k, esc[k], c)[1], 3)
                  for k in (range(len(esc)) if ks is None else ks)}
    finally:
        c.cerrar()
    return salida, c.error


def causas(m, ruta, ks):
    """{k: [mecanismos cuya retirada hace cumplir el escenario k]}."""
    salida = {k: [] for k in ks}
    for tipo in m.prob['espec']['tipos']:
        prob = dict(m.prob, espec=retirar(m.prob['espec'], tipo))
        fr, _ = fracciones(m, ruta, prob, ks)
        for k, x in fr.items():
            if x >= G.CUMPLE:
                salida[k].append(tipo)
    return salida


def taller_de(r, f):
    sub = str(f['orden']) if f['fase'] == 'construccion' else f['problema']
    return Path(r) / 'talleres' / f['secuencia'] / f['rama'] / sub


def auditar(f, origen, prob):
    """Ficha de auditoría de un episodio (sin modelo)."""
    vals = f.get('validaciones') or []
    ficha = {'rama': f['rama'], 'problema': f['problema'], 'tipos': prob['espec']['tipos'], 'cumple': f['puntuacion'] >= 0.9,
             'incompleto': bool(f.get('incompleto')), 'validaciones': [], 'pasos': f['pasos']}
    with tempfile.TemporaryDirectory() as tmp:
        m = E.Mundo(prob, Path(tmp) / 'taller', Presupuesto(maximo=0), almacen=None)
        for p in origen.rglob('*'):
            rel = p.relative_to(origen)
            if p.is_file() and rel.parts[0] != '.sistema' and '__pycache__' not in rel.parts:
                (m.taller / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, m.taller / rel)
        if f.get('codigo_entregado'):
            (m.taller / 'auditoria_entregado.py').write_text(f['codigo_entregado'])
        for i, v in enumerate(vals):
            fila = {'n': i + 1, 'ruta': v['ruta'], 'cumplidos': v['cumplidos'], 'verificada': False}
            if (m.taller / v['ruta']).is_file():
                fr, err = fracciones(m, v['ruta'], m.prob)
                fila['verificada'] = not err and [fr[k] for k in sorted(fr)] == [round(x, 3) for x in v['fracciones']]
            if v['cumplidos'] < FALLIDA and fila['verificada']:
                fallidos = [k for k, x in enumerate(v['fracciones']) if x < G.CUMPLE]
                fila['causas'] = causas(m, v['ruta'], fallidos)
                fila['codigo'] = (m.taller / v['ruta']).read_text()
                if f.get('codigo_entregado'):
                    fe, _ = fracciones(m, 'auditoria_entregado.py', m.prob, fallidos)
                    fila['entregado_cumple'] = {k: x >= G.CUMPLE for k, x in fe.items()}
                    fila['entregado_causas'] = causas(m, 'auditoria_entregado.py',
                                                      [k for k, ok in fila['entregado_cumple'].items() if not ok])
                    fila['cobertura'] = round(cobertura(f['codigo_entregado'], fila['codigo']), 2)
            ficha['validaciones'].append(fila)
    ficha['clase'] = clasificar(ficha, f)
    for v in ficha['validaciones']:
        v.pop('codigo', None)
    return ficha


def clasificar(ficha, f):
    fallidas = [v for v in ficha['validaciones'] if v['cumplidos'] < FALLIDA]
    if ficha['cumple']:
        return 'recuperado' if fallidas else 'sin fallo visible'
    if ficha['incompleto']:
        return 'recursos'
    if not fallidas:
        return 'sin señal'
    if not all(v['verificada'] for v in fallidas) or 'cobertura' not in fallidas[-1]:
        return 'indeterminado'
    ultima = fallidas[-1]                                      # la explicación con la que se quedó
    m_causa = {t for ts in ultima['causas'].values() for t in ts}
    persiste = {t for ts in ultima['entregado_causas'].values() for t in ts} & m_causa
    sobraban = (len(ficha['validaciones']) < RECURSOS['validaciones'] or
                G.PRESUPUESTO_PASOS - ficha['pasos'] >= RECURSOS['pasos'])
    if ultima['cobertura'] >= UMBRAL and persiste and sobraban:
        return 'anclaje'
    if ultima['cobertura'] < UMBRAL:
        return 'revisión insuficiente'
    return 'misma estructura, sin causa persistente aislable' if not persiste else 'misma estructura, sin recursos'


def main():
    r, banco = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text())
    tipos = {p['semilla']: p['tipos'] for s in banco for c in ('construccion', 'afines', 'ajenos') for p in s[c]}
    filas = [json.loads(l) for l in (r / 'registro.jsonl').read_text().splitlines()]
    fichas = []
    for f in filas:
        if f['rama'] not in CON_VALIDAR:
            continue
        prob = G.construir(f['problema'], tipos[f['problema']])
        fichas.append(auditar(f, taller_de(r, f), prob))
    print('Auditoría de anclaje (notas/diseno-descubrimiento.md §1). Una línea por episodio:')
    print('rama | problema | tipos | cumple | clase | validaciones (n: cumplidos, verificada, causas de los escenarios '
          'fallidos → el entregado sigue fallando por, cobertura entregado/fallido)')
    for x in fichas:
        vs = []
        for v in x['validaciones']:
            t = f'{v["n"]}: {v["cumplidos"]}/6{"" if v["verificada"] else " (no verificada)"}'
            if 'causas' in v:
                c = Counter(m for ts in v['causas'].values() for m in ts)
                t += f' causas {dict(c) or "ninguna aislable"}'
                if 'entregado_causas' in v:
                    ce = Counter(m for ts in v['entregado_causas'].values() for m in ts)
                    t += (f' → entregado falla {sum(not ok for ok in v["entregado_cumple"].values())}/'
                          f'{len(v["entregado_cumple"])} por {dict(ce) or "—"}, cobertura {v["cobertura"]}')
            vs.append(t)
        print(f'  {x["rama"]} | {x["problema"]} | {",".join(x["tipos"])} | {"sí" if x["cumple"] else "no"} | '
              f'{x["clase"]} | {"; ".join(vs) or "sin validaciones"}')
    print('\nResumen por clase (episodios):')
    for clase, n in Counter(x['clase'] for x in fichas).most_common():
        ramas = Counter(x['rama'] for x in fichas if x['clase'] == clase)
        print(f'  {clase}: {n} ({", ".join(f"{k} {v}" for k, v in sorted(ramas.items()))})')
    print('\nCausas de las validaciones fallidas verificadas (escenarios):')
    c = Counter(m for x in fichas for v in x['validaciones'] for ts in v.get('causas', {}).values() for m in ts)
    sin = sum(1 for x in fichas for v in x['validaciones'] for ts in v.get('causas', {}).values() if not ts)
    print(f'  {dict(c)}; escenarios sin causa aislable: {sin}')


if __name__ == '__main__':
    main()
