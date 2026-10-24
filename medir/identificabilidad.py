"""¿Permitían los datos de una validación distinguir la causa de su fallo de otras explicaciones? Sin gasto
(notas/diseno-descubrimiento.md §3; criterio fijado antes de correr).

Para cada par (validación fallida, mecanismo M que causó el fallo) se enumeran explicaciones alternativas: la
verdadera sin M, y sin M pero con otro mecanismo M' que no tiene. Cada una se ajusta a las lecturas de los 6
escenarios, con las acciones registradas, minimizando el error cuadrático medio (RMS, método de Powell, varios
arranques). La verdadera se reajusta igual, para conocer el suelo del ajuste.
- Libres: los parámetros continuos de los mecanismos (ganancias, memoria, deriva, umbrales, límite) y, por escenario,
  el estado inicial, la deriva inicial y el tamaño de la perturbación.
- Lo discreto (canal, actuador, retardos, régimen inicial, instante de la perturbación) sale de la verdad cuando se
  comparte y se sortea entre arranques cuando no. Partir de la verdad favorece a las alternativas.
- Una alternativa explica igual si su RMS ≤ max(IGUAL_ABS, IGUAL_REL × RMS de la verdadera). M es no identificable si
  alguna explica igual (concluyente) e identificable si ninguna lo consigue (provisional).

python -m medir.identificabilidad cordura
python -m medir.identificabilidad resultados/maq-retro-piloto bancos/maquinas/retro_piloto.json [ramas]
"""
import copy
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from base import maquinas_retro as RT
from generadores import maquinas as G

IGUAL_ABS = 0.04           # el doble del ruido de lectura (0,02)
IGUAL_REL = 1.5
ARRANQUES = 4
MAX_EVAL = 2500


def _observado(prob, trayectorias):
    esc = RT.escenarios_validacion(prob)
    return [(esc[t['escenario'] - 1], [p['acciones'] for p in t['pasos']], np.array([p['lecturas'] for p in t['pasos']]))
            for t in trayectorias]


class Explicacion:
    """Un conjunto de mecanismos con sus parámetros discretos fijos y un vector de continuos que se ajusta."""

    def __init__(self, tipos, prob, obs, rng, desde_verdad=True):
        self.tipos, self.obs = sorted(tipos), obs
        verdad = prob['espec']
        muestra = G.especificar(rng, self.tipos, prob['objetivo'])        # parámetros de lo que la verdad no tiene
        e = copy.deepcopy(muestra)
        for clave in ('G',) + tuple(c for t, c in (('acumulador', 'lam'), ('deriva', 'deriva'), ('retardo', 'retardo'),
                                                   ('aliasing', 'aliasing'), ('histeresis', 'histeresis'),
                                                   ('saturacion', 'saturacion'), ('modo', 'modo'))
                                    if t in self.tipos and t in verdad['tipos']):
            if desde_verdad:
                e[clave] = copy.deepcopy(verdad[clave])
        e['ruido'] = 0.0
        self.espec = e
        self.inis = []
        for ini_v, _, _ in obs:
            ini = copy.deepcopy(ini_v)
            if not desde_verdad:
                ini['h'] = [rng.uniform(-2, 2) for _ in range(G.N_CAN)]
                ini['d'] = [rng.uniform(-0.8, 0.8) for _ in range(G.N_CAN)]
            ini['modo'] = (ini_v.get('modo', 0) if 'modo' in verdad['tipos'] else rng.randrange(2)) if e['modo'] else 0
            signo = (1 if ini_v.get('histe', 0) >= 0 else -1) if 'histeresis' in verdad['tipos'] else rng.choice([-1, 1])
            ini['_signo_histe'] = signo
            self.inis.append(ini)

    # vector de continuos ------------------------------------------------------------------------------------------
    def empaquetar(self):
        e, x = self.espec, list(np.array(self.espec['G']).ravel())
        if 'acumulador' in self.tipos:
            x += e['lam']
        if 'deriva' in self.tipos:
            x += e['deriva']
        if 'histeresis' in self.tipos:
            x += [e['histeresis']['salto'], e['histeresis']['alto'], e['histeresis']['bajo']]
        if 'saturacion' in self.tipos:
            x += [e['saturacion']['limite']]
        for ini in self.inis:
            x += list(ini['h']) + list(ini['d']) + [ini['perturbacion'][2]]
        return np.array(x, float)

    def desempaquetar(self, x):
        e, i = copy.deepcopy(self.espec), 4
        e['G'] = [list(x[0:2]), list(x[2:4])]
        if 'acumulador' in self.tipos:
            e['lam'] = [min(0.99, max(0.0, v)) for v in x[i:i + 2]]
            i += 2
        if 'deriva' in self.tipos:
            e['deriva'] = list(x[i:i + 2])
            i += 2
        if 'histeresis' in self.tipos:
            e['histeresis'] = dict(e['histeresis'], salto=abs(x[i]), alto=x[i + 1], bajo=x[i + 2])
            i += 3
        if 'saturacion' in self.tipos:
            e['saturacion'] = dict(e['saturacion'], limite=abs(x[i]))
            i += 1
        inis = []
        for ini in self.inis:
            n = dict(ini, h=list(x[i:i + 2]), d=list(x[i + 2:i + 4]),
                     perturbacion=(ini['perturbacion'][0], ini['perturbacion'][1], x[i + 4]))
            n['histe'] = n['_signo_histe'] * e['histeresis']['salto'] if e['histeresis'] else 0.0
            inis.append(n)
            i += 5
        return e, inis

    def rms(self, x):
        e, inis = self.desempaquetar(x)
        total, n = 0.0, 0
        for ini, (_, acciones, lect) in zip(inis, self.obs):
            m = G.Maquina(e, ini, 'ajuste')
            m.lecturas()
            sim = np.array([m.paso(a) for a in acciones])
            total += float(((sim - lect) ** 2).sum())
            n += lect.size
        return math.sqrt(total / n)


def ajustar(tipos, prob, obs, arranques=ARRANQUES, max_eval=MAX_EVAL, semilla=0):
    mejor = math.inf
    for r in range(arranques):
        ex = Explicacion(tipos, prob, obs, random.Random(f'{semilla}-{"-".join(sorted(tipos))}-{r}'), desde_verdad=True)
        x0 = ex.empaquetar()
        if r:                                       # arranques siguientes: la verdad compartida con un poco de ruido
            x0 = x0 + np.random.default_rng(r).normal(0, 0.15, x0.size)
        res = minimize(ex.rms, x0, method='Powell', options={'maxfev': max_eval, 'xtol': 1e-3, 'ftol': 1e-7})
        mejor = min(mejor, float(res.fun), ex.rms(x0))
    return mejor


def alternativas(verdad, M):
    sin = [t for t in verdad if t != M]
    return [sin] + [sin + [o] for o in G.TIPOS if o not in verdad]


def identificar(prob, trayectorias, M, **kw):
    """{'rms_verdad', 'alternativas': {tipos: rms}, 'mejor': (tipos, rms), 'identificable': bool}."""
    obs = _observado(prob, trayectorias)
    verdad = prob['espec']['tipos']
    rv = ajustar(verdad, prob, obs, arranques=1, **kw)
    alts = {','.join(a) or '(ninguno)': ajustar(a, prob, obs, **kw) for a in alternativas(verdad, M)}
    umbral = max(IGUAL_ABS, IGUAL_REL * rv)
    nombre, r = min(alts.items(), key=lambda kv: kv[1])
    return {'rms_verdad': rv, 'umbral': umbral, 'alternativas': alts, 'mejor': (nombre, r), 'identificable': r > umbral}


def _trayectorias(prob, controlar):
    return [{'escenario': k + 1, 'pasos': RT.escenario_validacion(prob, k, ini, controlar)[0]}
            for k, ini in enumerate(RT.escenarios_validacion(prob))]


def _extremos(lec, mem):
    """Cambia de régimen en los dos sentidos cada 20 pasos (mantiene ±2,95 tres pasos) y si no, acciones moderadas."""
    t = mem.get('t', 0)
    mem['t'] = t + 1
    return [2.95, 2.95] if t % 20 < 3 else [-2.95, -2.95] if 10 <= t % 20 < 13 else [0.6, -0.6]


def cordura():
    """Dos casos con respuesta conocida (diseño §3). Devuelve [(caso, esperado, resultado)]."""
    from medir.evidencia import evidencia
    salida = []
    p = G.construir('ident-modo', ['modo'])
    r = identificar(p, _trayectorias(p, _extremos), 'modo')
    salida.append(('modo excitado con acciones extremas', True, r))
    for i in range(200):                       # una saturación que las lecturas nunca alcanzan
        p = G.construir(f'ident-sat-{i}', ['saturacion'])
        tr = _trayectorias(p, lambda lec, mem: [0.0, 0.0])
        if evidencia(p, tr)[0]['saturacion'] < 0.005:
            break
    r = identificar(p, tr, 'saturacion')
    salida.append((f'saturación no alcanzada ({p["semilla"]})', False, r))
    for i in range(200):                       # un modo que nunca cambia y empieza igual en todos los escenarios
        p = G.construir(f'ident-modo-fijo-{i}', ['modo'])
        if len({ini['modo'] for ini in RT.escenarios_validacion(p)}) == 1:
            break
    r = identificar(p, _trayectorias(p, lambda lec, mem: [0.6, -0.6]), 'modo')
    salida.append((f'modo que no cambia ni difiere entre escenarios ({p["semilla"]})', False, r))
    return salida


def main():
    if sys.argv[1] == 'cordura':
        for caso, esperado, r in cordura():
            print(f'{caso}: esperado {"identificable" if esperado else "no identificable"}; resultado '
                  f'{"identificable" if r["identificable"] else "no identificable"} '
                  f'{"(BIEN)" if r["identificable"] == esperado else "(MAL)"} | RMS verdad {r["rms_verdad"]:.3f}, '
                  f'umbral {r["umbral"]:.3f}, mejor alternativa {r["mejor"][0]} {r["mejor"][1]:.3f}')
        return
    from medir import anclaje as AN
    r, banco = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text())
    ramas = sys.argv[3].split(',') if len(sys.argv) > 3 else ['RETRO_SIN_ALMACEN', 'T0']
    tipos = {p['semilla']: p['tipos'] for s in banco for c in ('construccion', 'afines', 'ajenos') for p in s[c]}
    print(f'Identificabilidad de las causas de las validaciones fallidas (ramas {", ".join(ramas)}).')
    print('rama | problema | validación | causa M | RMS verdad reajustada | umbral | mejor alternativa (RMS) | veredicto')
    cuenta = {True: 0, False: 0}
    for linea in (r / 'registro.jsonl').read_text().splitlines():
        f = json.loads(linea)
        if f['rama'] not in ramas or not f.get('validaciones'):
            continue
        prob = G.construir(f['problema'], tipos[f['problema']])
        origen = AN.taller_de(r, f)
        ficha = AN.auditar(f, origen, prob)
        for fv in ficha['validaciones']:
            causas = sorted({M for ts in fv.get('causas', {}).values() for M in ts})
            for M in causas:
                t0 = time.time()
                tr = json.loads((origen / 'validaciones' / f'{fv["n"]}.json').read_text())
                res = identificar(prob, tr, M)
                cuenta[res['identificable']] += 1
                print(f'  {f["rama"]} | {f["problema"]} | {fv["n"]} | {M} | {res["rms_verdad"]:.3f} | {res["umbral"]:.3f} | '
                      f'{res["mejor"][0]} ({res["mejor"][1]:.3f}) | '
                      f'{"identificable (provisional)" if res["identificable"] else "NO identificable"} | '
                      f'{time.time() - t0:.0f} s', flush=True)
    print(f'\nIdentificables (provisional): {cuenta[True]}; no identificables (concluyente): {cuenta[False]}.')


if __name__ == '__main__':
    main()
