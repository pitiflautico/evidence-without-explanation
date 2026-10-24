"""Auditoría de oportunidades del laboratorio B, sin gasto (dueño 23/10): ¿había una capacidad reutilizable, barata y
eficaz que el modelo no construyó?

La capacidad es un instrumento de diagnóstico del banco, no algo que se entregue al modelo. Se construye solo con lo
que el resolutor tenía: la máquina de exploración (con cargo a los mismos 400 pasos), las lecturas, el objetivo y la
tolerancia. No mira la especificación ni los escenarios retenidos.

Capacidad (`herramienta`), genérica para cualquier máquina de la clase:
1. reinicio de régimen: mantiene los dos actuadores en -3 durante 3 pasos al empezar, en la exploración y en cada
   escenario (si una secuencia de acciones extremas cambia de régimen, la máquina queda en uno conocido), y después
   no pasa de ±2,8 (no vuelve a cambiarlo);
2. identificación por escalones: ganancia de cada actuador y tiempo hasta la mitad de la respuesta;
3. control integral con la inversa de la ganancia y la constante dividida por (1 + ese tiempo).
La constante (k = 0,8) se eligió solo con los 8 problemas de construcción del piloto (0,3 / 0,5 / 0,8 / 1,2); los
afines, los ajenos y los problemas nuevos no se miraron para elegirla. Una variante con autoselección por ensayo en la
máquina viva se probó y se descartó (empeora: un solo estado inicial no representa los escenarios).

Ablación: sin reinicio (y límite ±3). Problemas nuevos: semillas «auditoria-…», generados con las mismas reglas del
banco (el ideal resuelve; estrato por las referencias).

python -m medir.oportunidades_maquinas [n_recurrentes n_faciles n_ajenos] > resultados/maq-oportunidades/...
"""
import inspect
import json
import random
import sys
from pathlib import Path

import numpy as np

from generadores import maquinas as G

K = 0.8
REINICIO = [[-G.LIMITE, -G.LIMITE]] * 3
LIMITE_TRAS_REINICIO = 2.8


def herramienta(prob, reinicio=True, k=K):
    """(puntuación en escenarios retenidos, pasos de exploración usados). Solo usa lo visible y la exploración."""
    controlar, pasos = controlador(prob, reinicio, k)
    return G.evaluar(prob, controlar), pasos


def controlador(prob, reinicio=True, k=K):
    """(controlar, pasos de exploración usados) construido por la capacidad."""
    m = G.maquina_exploracion(prob)
    obj = np.array(prob['objetivo'])
    pref = REINICIO if reinicio else []
    lim = LIMITE_TRAS_REINICIO if reinicio else G.LIMITE
    for u in pref:
        m.paso(u)

    def tramo(u, n):
        return np.array([m.paso(u) for _ in range(n)])
    y0 = tramo([0, 0], 25)[-4:].mean(0)
    B, d = [], 0
    for a in range(G.N_ACT):
        u = [0] * G.N_ACT
        u[a] = 1.5
        r = tramo(u, 30)
        cambio = r[-4:].mean(0) - y0
        B.append(cambio / 1.5)
        j = int(np.argmax(np.abs(cambio)))
        d = max(d, int(np.argmax(np.abs(r[:, j] - y0[j]) > 0.5 * abs(cambio[j]))))
        tramo([0] * G.N_ACT, 25)
    Bi = np.linalg.pinv(np.array(B).T)

    def controlar(lecturas, memoria):
        t = memoria.setdefault('t', 0)
        memoria['t'] = t + 1
        if t < len(pref):
            return pref[t]
        u = np.array(memoria.get('u', [0.0] * G.N_ACT)) + k / (1 + d) * Bi @ (obj - np.array(lecturas))
        memoria['u'] = list(np.clip(u, -lim, lim))
        return memoria['u']
    return controlar, m.t


def lineas_de_codigo():
    return sum(1 for l in inspect.getsource(herramienta).splitlines() if l.strip() and not l.strip().startswith(('#', '"""')))


def nuevos(n_recurrentes, n_faciles, n_ajenos, recurrentes=('histeresis', 'modo'), semilla='auditoria'):
    """Problemas nuevos con las reglas del banco: recurrentes (difíciles con los tipos de la secuencia del piloto),
    fáciles (solo acompañantes lineales) y ajenos (aliasing y saturación, difíciles)."""
    rng = random.Random(semilla)
    ajenos_t = [t for t in G.NO_LINEALES if t not in recurrentes]
    salida, n = [], 0
    for clase, cuantos in (('recurrente', n_recurrentes), ('facil', n_faciles), ('ajeno', n_ajenos)):
        hechos = 0
        while hechos < cuantos:
            n += 1
            acompanante = [rng.choice(G.LINEALES)] if rng.random() < 0.5 else []
            if clase == 'facil':
                tipos = acompanante
            else:
                fuente = list(recurrentes) if clase == 'recurrente' else ajenos_t
                tipos = rng.sample(fuente, rng.randint(1, len(fuente))) + acompanante
            prob = G.construir(f'{semilla}-{n}', tipos)
            cal = G.calibrar(prob)
            if cal['ideal'] < G.UMBRAL_IDEAL or cal['estrato'] != ('facil' if clase == 'facil' else 'dificil'):
                continue
            salida.append({'clase': clase, 'semilla': f'{semilla}-{n}', 'tipos': sorted(tipos), **cal})
            hechos += 1
    return salida


def _fila(clase, p, modelo=None):
    prob = G.construir(p['semilla'], p['tipos'])
    h, pasos = herramienta(prob)
    sr, _ = herramienta(prob, reinicio=False)
    return {'clase': clase, 'semilla': p['semilla'], 'tipos': p['tipos'], 'estrato': p['estrato'],
            'ideal': p['ideal'], 'ingenuo': p['ingenuo'], 'generico': p['generico'], 'herramienta': h,
            'sin_reinicio': sr, 'pasos': pasos, 'modelo': modelo}


def resumen(filas, titulo):
    print(f'\n{titulo}')
    print('  grupo | n | cumplidos (≥0,9): herramienta / sin reinicio / ingenuo / genérico / modelo | media herramienta')
    grupos = {}
    for f in filas:
        grupos.setdefault((f['clase'], f['estrato']), []).append(f)
    for (clase, estrato), fs in grupos.items():
        c = lambda campo: sum(f[campo] is not None and f[campo] >= G.UMBRAL_IDEAL for f in fs)
        mod = c('modelo') if all(f['modelo'] is not None for f in fs) else '—'
        print(f'  {clase} {estrato} | {len(fs)} | {c("herramienta")} / {c("sin_reinicio")} / {c("ingenuo")} / '
              f'{c("generico")} / {mod} | {np.mean([f["herramienta"] for f in fs]):.2f}')


def main():
    n_rec, n_fac, n_aje = (int(x) for x in sys.argv[1:4]) if len(sys.argv) > 3 else (30, 10, 10)
    raiz = Path(__file__).resolve().parent.parent
    banco = json.loads((raiz / 'bancos' / 'maquinas' / 'piloto.json').read_text())[0]
    registro = raiz / 'resultados' / 'maq-piloto' / 'registro.jsonl'
    mejor = {}
    for l in registro.read_text().splitlines():
        f = json.loads(l)
        if f['fase'] in ('construccion', 'trasplante'):
            mejor[f['problema']] = max(mejor.get(f['problema'], 0.0), f['puntuacion'])
    print(f'Capacidad: {lineas_de_codigo()} líneas; k = {K} (elegida solo con construcción).')
    piloto = [_fila(c, p, mejor.get(p['semilla'])) for c in ('construccion', 'afines', 'ajenos') for p in banco[c]]
    print('\nProblemas del piloto (modelo = mejor puntuación de cualquier rama o brazo en ese problema):')
    for f in piloto:
        print(f'  {f["clase"][:5]} {f["semilla"]:7} {f["estrato"][:3]} {",".join(f["tipos"]):28} herramienta '
              f'{f["herramienta"]:.2f} | sin reinicio {f["sin_reinicio"]:.2f} | ingenuo {f["ingenuo"]:.2f} | genérico '
              f'{f["generico"]:.2f} | modelo {f["modelo"]:.2f} | pasos {f["pasos"]}')
    resumen([f for f in piloto if f['clase'] == 'construccion'], 'Piloto, construcción (usado para elegir k):')
    resumen([f for f in piloto if f['clase'] != 'construccion'], 'Piloto, prueba (no usado para elegir nada):')
    frescos = [_fila(p['clase'], p) for p in nuevos(n_rec, n_fac, n_aje)]
    resumen(frescos, f'Problemas nuevos (semillas «auditoria-…», no usados para elegir nada):')
    print('\nNuevos, uno a uno:')
    for f in frescos:
        print(f'  {f["clase"]:10} {f["semilla"]:14} {",".join(f["tipos"]):28} herramienta {f["herramienta"]:.2f} | '
              f'sin reinicio {f["sin_reinicio"]:.2f} | ingenuo {f["ingenuo"]:.2f} | genérico {f["generico"]:.2f}')


if __name__ == '__main__':
    main()
