"""Auditoría de la histéresis en el piloto A / A_PISTA / A+ / X (notas/diseno-a-aplus-x.md §13; criterios fijados antes
de calcular). Sin gasto: solo el simulador, que es determinista, y los registros del piloto.

python -m medir.histeresis_piloto episodios resultados/hipotesis-piloto <ciego> <clave.json>   # P1, P2.1 y clase
python -m medir.histeresis_piloto identificar resultados/hipotesis-piloto                        # P2.2 (lento)
python -m medir.histeresis_piloto oportunidad resultados/hipotesis-piloto                        # P3
python -m medir.histeresis_piloto envoltorio resultados/hipotesis-piloto                         # P3 bis (post hoc)

P3 bis es exploratorio y se añadió después de ver P3 (no estaba en los criterios fijados): el controlador que entregó
el propio modelo, precedido de 3 pasos con los actuadores en +3 o en −3 (una operación genérica de «llevar la máquina
a un extremo antes de controlar»). Elegir el signo le costaría al modelo una validación.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

from base import maquinas_entorno as E
from base import maquinas_retro as RT
from ejecutor.agente import Presupuesto
from generadores import maquinas as G
from medir import anclaje as AN
from medir import identificabilidad as I
from medir import oportunidades_maquinas as O

H = 'histeresis'


def _filas(carpeta):
    return [json.loads(l) for l in (Path(carpeta) / 'registro.jsonl').read_text().splitlines() if l.strip()]


def _cambios(maq, acciones):
    """Cambios de rama de la histéresis al aplicar las acciones a la máquina."""
    n, rama = 0, maq.histe
    for u in acciones:
        maq.paso(u)
        n += maq.histe != rama
        rama = maq.histe
    return n


def cambios_exploracion(prob, taller):
    """Cambios de rama en la exploración del modelo, reproducida en la máquina verdadera con sus reinicios."""
    maq, n = G.maquina_exploracion(prob), 0
    ruta = Path(taller) / 'exploracion.jsonl'
    for l in (ruta.read_text().splitlines() if ruta.exists() else []):
        a = json.loads(l)
        if a['reiniciar']:
            maq = G.maquina_exploracion(prob)
        n += _cambios(maq, a['secuencia'])
    return n


def _trayectorias(taller, n):
    return json.loads((Path(taller) / 'validaciones' / f'{n}.json').read_text())


def cambios_validacion(prob, trayectorias):
    esc = RT.escenarios_validacion(prob)
    return sum(_cambios(G.Maquina(prob['espec'], esc[t['escenario'] - 1], f'ruido-val-{prob["semilla"]}-{t["escenario"] - 1}'),
                        [p['acciones'] for p in t['pasos']]) for t in trayectorias)


def _f4(ciego, clave):
    mapa = json.loads(Path(clave).read_text())
    return {(e['problema'], e['brazo']): any(a['familia'] == 'F4' for a in
                                              json.loads((Path(ciego) / f'{c}.json').read_text())['afirmaciones'])
            for c, e in mapa.items()}


def auditar(f, prob, taller):
    sin_h = dict(prob, espec=AN.retirar(prob['espec'], H))
    ficha = {'problema': f['problema'], 'brazo': f['brazo'], 'puntuacion': f['puntuacion'], 'pasos': f['pasos'],
             'validaciones_usadas': len(f['validaciones']), 'validaciones': [],
             'cambios_exploracion': cambios_exploracion(prob, taller)}
    with tempfile.TemporaryDirectory() as tmp:
        m = E.Mundo(prob, Path(tmp) / 'taller', Presupuesto(maximo=0), almacen=None)
        for p in Path(taller).rglob('*'):
            rel = p.relative_to(taller)
            if p.is_file() and rel.parts[0] != '.sistema' and '__pycache__' not in rel.parts:
                (m.taller / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, m.taller / rel)
        for i, v in enumerate(f['validaciones'], 1):
            tr = _trayectorias(taller, i)
            fila = {'n': i, 'cumplidos': v['cumplidos'], 'cambios': cambios_validacion(prob, tr), 'verificada': False}
            fr, err = AN.fracciones(m, v['ruta'], prob) if (m.taller / v['ruta']).is_file() else ({}, 'falta')
            fila['verificada'] = not err and [fr[k] for k in sorted(fr)] == [round(x, 3) for x in v['fracciones']]
            if fila['verificada'] and v['cumplidos'] < len(v['fracciones']):
                fallidos = [k for k, x in enumerate(v['fracciones']) if x < G.CUMPLE]
                causas = AN.causas(m, v['ruta'], fallidos)
                fila['fallidos'], fila['por_h'] = len(fallidos), sum(H in c for c in causas.values())
            ficha['validaciones'].append(fila)
        if f.get('codigo_entregado'):
            (m.taller / 'auditoria_entregado.py').write_text(f['codigo_entregado'])
            for nombre, p in (('entregado_con', prob), ('entregado_sin', sin_h)):
                c = m.controlador('auditoria_entregado.py')
                try:
                    ficha[nombre] = 0.0 if c.error else G.evaluar(p, c)
                finally:
                    c.cerrar()
    ficha['cambios_validacion'] = sum(v['cambios'] for v in ficha['validaciones'])
    gana = ficha.get('entregado_sin', 0) - ficha.get('entregado_con', 0) >= 1 / len(prob['escenarios']) - 1e-9
    ficha['influye'] = gana or any(v.get('por_h', 0) for v in ficha['validaciones'])
    ficha['decide'] = ficha.get('entregado_sin', 0) >= G.UMBRAL_IDEAL > ficha.get('entregado_con', 0)
    return ficha


def clase(ficha, f4):
    if ficha['puntuacion'] >= G.UMBRAL_IDEAL:
        return 'cumple'
    if not ficha['influye']:
        return 'no influye'
    if ficha['cambios_exploracion'] + ficha['cambios_validacion'] == 0:
        return 'exploración'
    return 'acción' if f4 else 'interpretación'


def episodios(carpeta, ciego, clave):
    carpeta = Path(carpeta)
    f4 = _f4(ciego, clave)
    lineas = ['problema | brazo | puntuación | entregado con / sin H | validaciones (cumplidos, escenarios por H / '
              'fallidos, cambios de rama) | cambios en exploración | pasos | F4 | influye | decide | clase']
    fichas = []
    for f in _filas(carpeta):
        if H not in f['tipos']:
            continue
        prob = G.construir(f['problema'], f['tipos'])
        fi = auditar(f, prob, carpeta / 'talleres' / f['problema'] / f['brazo'])
        fi['f4'], fi['clase'] = f4[(f['problema'], f['brazo'])], clase(fi, f4[(f['problema'], f['brazo'])])
        fichas.append(fi)
        vs = '; '.join(f'{v["cumplidos"]}/6' + (f' {v["por_h"]}/{v["fallidos"]}' if 'fallidos' in v else '') +
                       f' c{v["cambios"]}' + ('' if v['verificada'] else ' (no verificada)') for v in fi['validaciones'])
        lineas.append(f'{fi["problema"]} | {fi["brazo"]} | {fi["puntuacion"]:.3f} | '
                      f'{fi.get("entregado_con", float("nan")):.3f} / {fi.get("entregado_sin", float("nan")):.3f} | '
                      f'{vs or "—"} | {fi["cambios_exploracion"]} | {fi["pasos"]} | {"sí" if fi["f4"] else "no"} | '
                      f'{"sí" if fi["influye"] else "no"} | {"sí" if fi["decide"] else "no"} | {fi["clase"]}')
    lineas.append('')
    for c in ('cumple', 'no influye', 'exploración', 'interpretación', 'acción'):
        lineas.append(f'{c}: {sum(x["clase"] == c for x in fichas)} de {len(fichas)}')
    lineas.append(f'influye: {sum(x["influye"] for x in fichas)}; decide el fallo final: {sum(x["decide"] for x in fichas)}')
    return lineas, fichas


def identificar(carpeta):
    """P2.2: identificabilidad de la histéresis en cada validación fallida donde fue causa de algún escenario."""
    carpeta = Path(carpeta)
    lineas = ['problema | brazo | validación | RMS verdad | umbral | mejor alternativa (RMS) | veredicto']
    for f in _filas(carpeta):
        if H not in f['tipos'] or f['puntuacion'] >= G.UMBRAL_IDEAL:
            continue
        prob = G.construir(f['problema'], f['tipos'])
        fi = auditar(f, prob, carpeta / 'talleres' / f['problema'] / f['brazo'])
        for v in fi['validaciones']:
            if v.get('por_h'):
                r = I.identificar(prob, _trayectorias(carpeta / 'talleres' / f['problema'] / f['brazo'], v['n']), H)
                lineas.append(f'{f["problema"]} | {f["brazo"]} | {v["n"]} | {r["rms_verdad"]:.3f} | {r["umbral"]:.3f} | '
                              f'{r["mejor"][0]} ({r["mejor"][1]:.3f}) | '
                              f'{"identificable" if r["identificable"] else "NO identificable"}')
                print(lineas[-1], flush=True)
    return lineas


def oportunidad(carpeta):
    """P3: la capacidad genérica, con y sin reinicio de régimen, en cada problema con histéresis."""
    vistos, lineas = set(), ['problema | tipos | capacidad (pasos) | sin reinicio (pasos) | oportunidad práctica']
    for f in _filas(carpeta):
        if H not in f['tipos'] or f['problema'] in vistos:
            continue
        vistos.add(f['problema'])
        prob = G.construir(f['problema'], f['tipos'])
        con, pc = O.herramienta(prob)
        sin, ps = O.herramienta(prob, reinicio=False)
        op = con >= G.UMBRAL_IDEAL and pc <= G.PRESUPUESTO_PASOS and sin < G.UMBRAL_IDEAL
        lineas.append(f'{f["problema"]} | {",".join(f["tipos"])} | {con:.3f} ({pc}) | {sin:.3f} ({ps}) | {"sí" if op else "no"}')
    return lineas


ENVOLTORIO = """from auditoria_entregado import controlar as _base


def controlar(lecturas, memoria):
    t = memoria.get('_auditoria_t', 0)
    memoria['_auditoria_t'] = t + 1
    if t < 3:
        return [{s}] * {n}
    return _base(lecturas, memoria)
"""


def envoltorio(carpeta):
    carpeta = Path(carpeta)
    lineas = ['problema | brazo | entregado | con +3 delante | con −3 delante | mejor ≥ 0,9']
    for f in _filas(carpeta):
        if H not in f['tipos'] or not f.get('codigo_entregado') or f['puntuacion'] >= G.UMBRAL_IDEAL:
            continue
        prob = G.construir(f['problema'], f['tipos'])
        with tempfile.TemporaryDirectory() as tmp:
            m = E.Mundo(prob, Path(tmp) / 'taller', Presupuesto(maximo=0), almacen=None)
            origen = carpeta / 'talleres' / f['problema'] / f['brazo']
            for p in origen.rglob('*.py'):
                rel = p.relative_to(origen)
                if rel.parts[0] != '.sistema':
                    (m.taller / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, m.taller / rel)
            (m.taller / 'auditoria_entregado.py').write_text(f['codigo_entregado'])
            r = {}
            for s in (G.LIMITE, -G.LIMITE):
                (m.taller / 'auditoria_envoltorio.py').write_text(ENVOLTORIO.format(s=s, n=G.N_ACT))
                r[s] = E.evaluar_controlador(m, 'auditoria_envoltorio.py')['puntuacion']
        lineas.append(f'{f["problema"]} | {f["brazo"]} | {f["puntuacion"]:.3f} | {r[G.LIMITE]:.3f} | {r[-G.LIMITE]:.3f} | '
                      f'{"sí" if max(r.values()) >= G.UMBRAL_IDEAL else "no"}')
    lineas.append(f'mejor ≥ 0,9: {sum(l.endswith("sí") for l in lineas)} de {len(lineas) - 1}')
    return lineas


def main():
    orden, carpeta = sys.argv[1], sys.argv[2]
    if orden == 'episodios':
        print('\n'.join(episodios(carpeta, sys.argv[3], sys.argv[4])[0]))
    elif orden == 'identificar':
        identificar(carpeta)
    elif orden == 'envoltorio':
        print('\n'.join(envoltorio(carpeta)))
    elif orden == 'oportunidad':
        print('\n'.join(oportunidad(carpeta)))


if __name__ == '__main__':
    main()
