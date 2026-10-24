"""Contrastar hipótesis propias con los datos observados (solo análisis: no propone hipótesis ni experimentos).

Una hipótesis es una función que escribes tú, `simular(x, acciones, k)`, que devuelve las lecturas que predice para
esa lista de acciones (una lectura por acción, con un valor por canal), y un vector inicial de parámetros `x0`. `k`
es el índice de la trayectoria, por si tu hipótesis necesita un estado inicial propio para cada una.

    from contraste import contrastar, cargar_datos, informe
    datos = cargar_datos()                      # exploración y validaciones de este taller
    r = contrastar({'h1': (simular1, x0_1), 'h2': (simular2, x0_2)}, datos)
    print(informe(r))

Para cada hipótesis busca los parámetros que mejor reproducen las lecturas (mínimo error cuadrático medio, RMS;
método de Powell con varios arranques) y devuelve el RMS, los parámetros y el RMS por trayectoria. Dice qué
hipótesis explican los datos casi igual de bien que la mejor (RMS no mayor que DISTINGUE veces el de la mejor): los
datos no permiten distinguirlas. El tiempo total está acotado por `segundos`.
"""
import json
import math
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

DISTINGUE = 1.5


def cargar_datos(fuentes=('exploracion', 'validaciones'), carpeta='.'):
    """[{'fuente', 'acciones', 'lecturas'}]: la exploración (un tramo continuo entre reinicios) y cada escenario de
    cada validación."""
    carpeta, datos = Path(carpeta), []
    if 'exploracion' in fuentes and (carpeta / 'exploracion.jsonl').exists():
        tramo = None
        for linea in (carpeta / 'exploracion.jsonl').read_text().splitlines():
            a = json.loads(linea)
            if tramo is None or a['reiniciar']:
                tramo = {'fuente': f'exploracion {len(datos) + 1}', 'acciones': [], 'lecturas': []}
                datos.append(tramo)
            tramo['acciones'] += a['secuencia']
            tramo['lecturas'] += a['lecturas']
    if 'validaciones' in fuentes:
        for ruta in sorted((carpeta / 'validaciones').glob('*.json'), key=lambda p: p.stem):
            if not ruta.stem.isdigit():
                continue
            for t in json.loads(ruta.read_text()):
                datos.append({'fuente': f'validacion {ruta.stem} escenario {t["escenario"]}',
                              'acciones': [p['acciones'] for p in t['pasos']],
                              'lecturas': [p['lecturas'] for p in t['pasos']]})
    return [d for d in datos if d['acciones']]


def _rms(simular, x, datos):
    total, n, por = 0.0, 0, []
    for k, d in enumerate(datos):
        pred = np.asarray(simular(np.asarray(x, float), d['acciones'], k), float)
        obs = np.asarray(d['lecturas'], float)
        if pred.shape != obs.shape:
            raise ValueError(f'simular devolvió forma {pred.shape} y las lecturas son {obs.shape} (trayectoria {k})')
        e = float(((pred - obs) ** 2).sum())
        if not math.isfinite(e):
            e = 1e12
        total, n = total + e, n + obs.size
        por.append(math.sqrt(e / obs.size))
    return math.sqrt(total / n), por


def contrastar(hipotesis, datos=None, segundos=40, arranques=3, max_eval=1500, semilla=0):
    datos = cargar_datos() if datos is None else datos
    if not datos:
        raise ValueError('no hay datos: actúa sobre la máquina o valida un controlador primero')
    fin = time.monotonic() + segundos
    salida, incompleto = {}, False
    for i, (nombre, (simular, x0)) in enumerate(hipotesis.items()):
        limite = time.monotonic() + (fin - time.monotonic()) / (len(hipotesis) - i)   # reparto del tiempo que queda
        x0 = np.atleast_1d(np.asarray(x0, float))
        r = {'rms': math.inf, 'x': x0.tolist(), 'evaluaciones': 0, 'error': None}
        evals = [0]

        def objetivo(x):
            if time.monotonic() > limite:
                raise TimeoutError
            evals[0] += 1
            return _rms(simular, x, datos)[0]
        rng = np.random.default_rng(semilla)
        for a in range(arranques):
            inicio = x0 if a == 0 else x0 + rng.normal(0, 1, x0.size) * (0.1 * np.abs(x0) + 0.1)
            try:
                v = objetivo(inicio)
                if v < r['rms']:
                    r['rms'], r['x'] = v, inicio.tolist()
                if x0.size:
                    res = minimize(objetivo, inicio, method='Powell', options={'maxfev': max_eval, 'xtol': 1e-4, 'ftol': 1e-8})
                    if res.fun < r['rms']:
                        r['rms'], r['x'] = float(res.fun), res.x.tolist()
            except TimeoutError:
                incompleto = r['incompleta'] = True
                break
            except Exception as e:                       # un fallo de la hipótesis no detiene las demás
                r['error'] = f'{type(e).__name__}: {e}'[:300]
                break
        r['evaluaciones'] = evals[0]
        if math.isfinite(r['rms']):
            r['rms_por_trayectoria'] = [round(v, 4) for v in _rms(simular, r['x'], datos)[1]]
        salida[nombre] = r
    validas = {n: r['rms'] for n, r in salida.items() if math.isfinite(r['rms'])}
    mejor = min(validas, key=validas.get) if validas else None
    return {'hipotesis': salida, 'mejor': mejor,
            'no_distinguibles_de_la_mejor': sorted(n for n, v in validas.items()
                                                   if n != mejor and v <= DISTINGUE * validas[mejor]),
            'trayectorias': [d['fuente'] for d in datos], 'incompleto': incompleto,
            'criterio': f'no distinguible: RMS <= {DISTINGUE} x RMS de la mejor'}


def informe(r):
    filas = [f'{len(r["trayectorias"])} trayectorias; {r["criterio"]}' + ('; TIEMPO AGOTADO (resultado parcial)' if r['incompleto'] else '')]
    for n, h in sorted(r['hipotesis'].items(), key=lambda kv: kv[1]['rms']):
        filas.append(f'  {n}: RMS {h["rms"]:.4f} ({h["evaluaciones"]} evaluaciones)'
                     + (f'; error: {h["error"]}' if h['error'] else '')
                     + (f'; x = {[round(v, 4) for v in h["x"]]}' if len(h['x']) <= 12 else ''))
    filas.append(f'mejor: {r["mejor"]}; no distinguibles de la mejor con estos datos: '
                 f'{", ".join(r["no_distinguibles_de_la_mejor"]) or "ninguna"}')
    return '\n'.join(filas)
