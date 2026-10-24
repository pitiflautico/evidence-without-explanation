"""¿Las pruebas del modelo hicieron visible lo que le impedía controlar? Sin gasto (notas/diseno-descubrimiento.md §2).

Dos magnitudes separadas (dueño 23/10):
- **Evidencia disponible** en una prueba sobre el mecanismo M: con las acciones que el modelo aplicó en cada escenario
  de validación, ¿cambian las lecturas si M no existiera? Se repiten las mismas acciones (en lazo abierto, con el mismo
  estado inicial y el mismo ruido) en la máquina verdadera y en la misma máquina sin M; la diferencia cuadrática media
  de las lecturas es D_M. M es visible si D_M > VISIBLE en algún escenario. Es una cota de lo que la prueba podía
  enseñar, no lo que el modelo aprendió: no es información obtenida.
- **Valor práctico** de M para ese episodio: M causa el fallo de su propio controlador (auditoría de anclaje: retirarlo
  hace cumplir el escenario).

El cruce responde a la pregunta del dueño: si lo que bloqueaba el control fue visible y aun así falló, faltó
convertir la evidencia en una solución; si no fue visible, faltó el experimento que la mostrara.

La información en sentido bayesiano (hipótesis y probabilidades a priori) queda pendiente: el estimador por
simulación probado (prototipo, §2 del diseño) es inestable justo donde la información es alta.

python -m medir.evidencia resultados/maq-retro-piloto bancos/maquinas/retro_piloto.json
"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

from base import maquinas_retro as RT
from generadores import maquinas as G
from medir import anclaje as AN

VISIBLE = 0.1          # 5 veces el ruido de lectura (0,02); fijado antes de mirar los datos


def lecturas(espec, ini, semilla, acciones):
    m = G.Maquina(espec, ini, semilla)
    m.lecturas()                       # como la validación: una lectura antes del primer paso (consume ruido)
    return [m.paso(a) for a in acciones]


def evidencia(prob, trayectorias):
    """{M: D_M máxima entre escenarios} y si la reproducción de la máquina verdadera coincide con lo registrado."""
    esc = RT.escenarios_validacion(prob)
    d, reproduce = {M: 0.0 for M in prob['espec']['tipos']}, True
    for tr in trayectorias:
        k = tr['escenario'] - 1
        acciones = [p['acciones'] for p in tr['pasos']]
        semilla = f'ruido-val-{prob["semilla"]}-{k}'
        verdad = lecturas(prob['espec'], esc[k], semilla, acciones)
        reproduce &= all(abs(a - b) < 1e-9 for v, r in zip(verdad, [p['lecturas'] for p in tr['pasos']])
                         for a, b in zip(v, r))
        for M in d:
            sin = lecturas(AN.retirar(prob['espec'], M), esc[k], semilla, acciones)
            rms = math.sqrt(sum((a - b) ** 2 for v, s in zip(verdad, sin) for a, b in zip(v, s)) / (len(verdad) * G.N_CAN))
            d[M] = max(d[M], rms)
    return d, reproduce


def main():
    r, banco = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text())
    tipos = {p['semilla']: p['tipos'] for s in banco for c in ('construccion', 'afines', 'ajenos') for p in s[c]}
    filas = [json.loads(l) for l in (r / 'registro.jsonl').read_text().splitlines()]
    print(f'Evidencia disponible en las validaciones (D_M > {VISIBLE}) y causas del fallo del propio controlador.\n')
    print('rama | problema | validación | cumplidos | mecanismos visibles (D_M) | causas del fallo | ¿causas visibles?')
    cruce, visibles_tot, reproducidas, total = Counter(), Counter(), 0, 0
    for f in filas:
        if f['rama'] not in AN.CON_VALIDAR or not f.get('validaciones'):
            continue
        prob = G.construir(f['problema'], tipos[f['problema']])
        origen = AN.taller_de(r, f)
        ficha = AN.auditar(f, origen, prob)
        for v, fv in zip(f['validaciones'], ficha['validaciones']):
            n = fv['n']
            ruta = origen / 'validaciones' / f'{n}.json'
            if not ruta.exists():
                continue
            d, reproduce = evidencia(prob, json.loads(ruta.read_text()))
            total += 1
            reproducidas += reproduce
            vis = {M for M, x in d.items() if x > VISIBLE}
            for M in prob['espec']['tipos']:
                visibles_tot[(M, M in vis)] += 1
            causas = {M for ts in fv.get('causas', {}).values() for M in ts}
            for M in causas:
                cruce[(f['rama'] in ('RETRO_SIN_ALMACEN', 'T0'), M in vis, ficha['cumple'])] += 1
            print(f'  {f["rama"]} | {f["problema"]} | {n} | {v["cumplidos"]}/6 | '
                  f'{", ".join(f"{M} {d[M]:.2f}" for M in sorted(d)) } | {", ".join(sorted(causas)) or "—"} | '
                  f'{", ".join(f"{M}: {"sí" if M in vis else "no"}" for M in sorted(causas)) or "—"}'
                  f'{"" if reproduce else " (no reproduce)"}')
    print(f'\nValidaciones analizadas: {total}; la máquina verdadera reproduce exactamente lo registrado en {reproducidas}.')
    print('\nMecanismos de cada máquina hechos visibles por las validaciones (validaciones en que lo fueron / en que existían):')
    for M in G.TIPOS:
        si, no = visibles_tot[(M, True)], visibles_tot[(M, False)]
        if si + no:
            print(f'  {M}: {si}/{si + no}')
    print('\nCausas de validaciones fallidas (mecanismo × validación), según fueran visibles en esa misma validación:')
    for a_like in (True, False):
        grupo = 'brazos tipo A (RETRO_SIN_ALMACEN, T0)' if a_like else 'resto de brazos'
        print(f'  {grupo}: visibles {sum(v for (a, vis, _), v in cruce.items() if a == a_like and vis)}, '
              f'no visibles {sum(v for (a, vis, _), v in cruce.items() if a == a_like and not vis)}; de ellas en episodios '
              f'que acabaron fallando: visibles {cruce[(a_like, True, False)]}, no visibles {cruce[(a_like, False, False)]}')


if __name__ == '__main__':
    main()
