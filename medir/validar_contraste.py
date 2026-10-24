"""Prueba de `contrastar` (base/taller/contraste.py) antes de dársela a A+ (notas/diseno-a-aplus-x.md §2.1).

Escribe como funciones `simular` las explicaciones que usó el auditor de identificabilidad (que sí conoce el catálogo;
aquí es legítimo, porque se prueba la herramienta, no se le da al modelo) y comprueba que `contrastar`, con los mismos
datos, llega al mismo veredicto: la causa es identificable si la explicación verdadera es la mejor y ninguna
alternativa queda dentro de DISTINGUE veces su RMS. El criterio de `contrastar` es solo relativo (el modelo no conoce
el ruido); el del auditor tiene además un suelo absoluto de 0,04, así que puede haber discrepancias cerca del umbral.

python -m medir.validar_contraste cordura
python -m medir.validar_contraste resultados/maq-retro-piloto bancos/maquinas/retro_piloto.json
"""
import json
import random
import sys
import time
from pathlib import Path

from base.taller import contraste as C
from generadores import maquinas as G
from medir import identificabilidad as I


def hipotesis(tipos, prob, obs, semilla=0):
    """(simular, x0) de una explicación del auditor, con lo discreto fijado como en su primer arranque."""
    ex = I.Explicacion(tipos, prob, obs, random.Random(f'{semilla}-{"-".join(sorted(tipos))}-0'), desde_verdad=True)

    def simular(x, acciones, k):
        e, inis = ex.desempaquetar(x)
        m = G.Maquina(e, inis[k], 'ajuste')
        m.lecturas()
        return [m.paso(a) for a in acciones]
    return simular, ex.empaquetar()


def veredicto(prob, trayectorias, M, segundos=600):
    obs = I._observado(prob, trayectorias)
    verdad = prob['espec']['tipos']
    hs = {'verdad': hipotesis(verdad, prob, obs)}
    for a in I.alternativas(verdad, M):
        hs[','.join(a) or '(ninguno)'] = hipotesis(a, prob, obs)
    datos = [{'fuente': f'escenario {t["escenario"]}', 'acciones': [p['acciones'] for p in t['pasos']],
              'lecturas': [p['lecturas'] for p in t['pasos']]} for t in trayectorias]
    t0 = time.time()
    r = C.contrastar(hs, datos, segundos=segundos, arranques=I.ARRANQUES, max_eval=I.MAX_EVAL)
    r['identificable'] = r['mejor'] == 'verdad' and not r['no_distinguibles_de_la_mejor']
    r['segundos'] = round(time.time() - t0)
    return r


def _linea(r):
    v = r['hipotesis']['verdad']['rms']
    otras = sorted((h['rms'], n) for n, h in r['hipotesis'].items() if n != 'verdad')
    return (f'verdad {v:.3f} | mejor alternativa {otras[0][1]} ({otras[0][0]:.3f}) | '
            f'{"identificable" if r["identificable"] else "NO identificable"} | {r["segundos"]} s')


def main():
    if sys.argv[1] == 'cordura':
        casos = [('modo excitado', True, 'ident-modo', ['modo'], I._extremos, 'modo')]
        p = G.construir('ident-sat-1', ['saturacion'])           # los mismos casos que medir.identificabilidad
        casos.append(('saturación no alcanzada', False, 'ident-sat-1', ['saturacion'], lambda l, m: [0.0, 0.0], 'saturacion'))
        casos.append(('modo fijo', False, 'ident-modo-fijo-26', ['modo'], lambda l, m: [0.6, -0.6], 'modo'))
        for nombre, esperado, semilla, tipos, ctrl, M in casos:
            p = G.construir(semilla, tipos)
            r = veredicto(p, I._trayectorias(p, ctrl), M)
            print(f'{nombre}: esperado {"identificable" if esperado else "no identificable"} | {_linea(r)} | '
                  f'{"BIEN" if r["identificable"] == esperado else "MAL"}', flush=True)
        return
    from medir import anclaje as AN
    r_, banco = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text())
    auditor = {}
    for f in ('identificabilidad_brazos_A.txt', 'identificabilidad_resto.txt'):
        for linea in (Path('resultados/descubrimiento-fase0') / f).read_text().splitlines():
            c = [x.strip() for x in linea.split('|')]
            if len(c) == 9:
                auditor[(c[0], c[1], c[2], c[3])] = c[7].startswith('identificable')
    tipos = {p['semilla']: p['tipos'] for s in banco for c in ('construccion', 'afines', 'ajenos') for p in s[c]}
    acuerdo = total = 0
    print('rama | problema | validación | M | contrastar | auditor | acuerdo')
    for linea in (r_ / 'registro.jsonl').read_text().splitlines():
        f = json.loads(linea)
        if f['rama'] not in AN.CON_VALIDAR or not f.get('validaciones'):
            continue
        prob = G.construir(f['problema'], tipos[f['problema']])
        origen = AN.taller_de(r_, f)
        for fv in AN.auditar(f, origen, prob)['validaciones']:
            for M in sorted({M for ts in fv.get('causas', {}).values() for M in ts}):
                tr = json.loads((origen / 'validaciones' / f'{fv["n"]}.json').read_text())
                r = veredicto(prob, tr, M)
                a = auditor[(f['rama'], f['problema'], str(fv['n']), M)]
                acuerdo, total = acuerdo + (a == r['identificable']), total + 1
                print(f'  {f["rama"]} | {f["problema"]} | {fv["n"]} | {M} | {_linea(r)} | '
                      f'{"identificable" if a else "NO identificable"} | {"sí" if a == r["identificable"] else "NO"}',
                      flush=True)
    print(f'\nAcuerdo con el auditor: {acuerdo} de {total}.')


if __name__ == '__main__':
    main()
