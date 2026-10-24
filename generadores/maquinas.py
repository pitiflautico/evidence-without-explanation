"""Máquinas desconocidas del laboratorio B (notas/diseno-simulador-b.md).

Una máquina tiene actuadores continuos (de -3 a 3), canales de salida y estado oculto. Cada paso:
    h_c ← λ_c·h_c + (1-λ_c)·((G·u_ef)_c + d_c)          (acoplamiento G; λ_c > 0 si hay acumulador)
    y_c = h_c + histéresis_c                             (salida verdadera, la que se evalúa)
    lectura_c = sensor_c(y_c) + ruido                    (lo que se ve: con aliasing o saturación si los hay)
Mecanismos (tipos del catálogo; el resolutor no recibe el catálogo): retardo, acumulador, histéresis, modo oculto
(una secuencia de acciones cambia de régimen y el régimen reasigna o invierte actuadores), aliasing, saturación y
deriva. Todo es determinista por semilla, incluido el ruido.

Objetivo verificable: entregar un controlador que, en escenarios retenidos (estado inicial, régimen y perturbación
que el resolutor nunca ve), mantenga cada salida en su franja durante la ventana final. Puntuación: fracción de
escenarios cumplidos, por código.

Garantías (dueño 22/10): se acepta una máquina si el controlador ideal (con acceso privilegiado al estado) cumple;
no se rechazan las fáciles: cada problema se etiqueta «facil» si lo resuelve un método convencional (ingenuo o
identificación lineal genérica con todo el presupuesto de pasos) y «dificil» si no; construir es una opción, no una
obligación.
"""
import copy
import itertools
import random

import numpy as np

LIMITE = 3.0
VALORES = tuple(range(-3, 4))                    # rejilla gruesa de búsqueda de las referencias
TIPOS = ('retardo', 'acumulador', 'histeresis', 'modo', 'aliasing', 'saturacion', 'deriva')
N_ACT, N_CAN = 2, 2
PASOS_ESCENARIO, VENTANA, CUMPLE = 60, 30, 0.9   # un escenario se cumple con ≥90 % de la ventana final en franja
N_ESCENARIOS = 12
PRESUPUESTO_PASOS = 400                          # interacción del resolutor con la máquina viva, por problema
UMBRAL_IDEAL, UMBRAL_FACIL = 0.9, 0.8
COMBOS = list(itertools.product(VALORES, repeat=N_ACT))


# --------------------------------------------------------------------------------------------------- especificación

def especificar(rng, tipos, objetivo):
    """Especificación JSON de una máquina con los tipos dados (acoplamiento siempre)."""
    while True:
        G = [[round(rng.choice([-1, 1]) * rng.uniform(0.4, 1.5), 2) for _ in range(N_ACT)] for _ in range(N_CAN)]
        if abs(np.linalg.det(np.array(G))) >= 0.5:
            break
    e = {'tipos': sorted(tipos), 'G': G, 'lam': [0.0] * N_CAN, 'retardo': [0] * N_ACT, 'histeresis': None,
         'modo': None, 'aliasing': [1] * N_CAN, 'saturacion': None, 'deriva': [0.0] * N_CAN,
         'ruido': 0.02, 'tol': 0.35}
    if 'acumulador' in tipos:
        e['lam'] = [round(rng.uniform(0.8, 0.93), 2) if rng.random() < 0.7 or c == 0 else 0.0 for c in range(N_CAN)]
    if 'retardo' in tipos:
        e['retardo'] = [rng.choice([2, 3, 4]) if a == 0 or rng.random() < 0.5 else 0 for a in range(N_ACT)]
    if 'histeresis' in tipos:
        # umbrales alrededor del objetivo: solo la rama alta es estable (h = objetivo - salto queda por encima de
        # bajo) y para llegar a ella hay que pasar de alto; la baja (h = objetivo + salto) cruza alto y salta
        c, salto = rng.randrange(N_CAN), round(rng.uniform(0.8, 1.5), 2)
        e['histeresis'] = {'canal': c, 'salto': salto, 'alto': round(objetivo[c] + rng.uniform(0.2, 0.6), 2),
                           'bajo': round(objetivo[c] - salto - rng.uniform(0.3, 0.7), 2)}
    if 'modo' in tipos:
        e['modo'] = {'actuador': rng.randrange(N_ACT), 'pasos': 2, 'permutar': rng.random() < 0.5,
                     'invertido': rng.randrange(N_ACT)}
    if 'aliasing' in tipos:
        e['aliasing'] = [rng.choice([3, 4]) if c == 0 or rng.random() < 0.5 else 1 for c in range(N_CAN)]
    if 'saturacion' in tipos:
        e['saturacion'] = {'canal': rng.randrange(N_CAN), 'limite': round(rng.uniform(0.6, 1.2), 2)}
    if 'deriva' in tipos:
        e['deriva'] = [round(rng.choice([-1, 1]) * rng.uniform(0.01, 0.03), 3) for _ in range(N_CAN)]
    return e


# --------------------------------------------------------------------------------------------------- dinámica

class Maquina:
    def __init__(self, espec, inicial, semilla_ruido):
        self.e = espec
        self.h = list(inicial['h'])
        self.d = list(inicial['d'])
        self.modo = inicial.get('modo', 0)
        self.histe = inicial.get('histe', 0.0)
        self.historial = [[0] * N_ACT for _ in range(max(espec['retardo']) + 1)]
        self.racha = [0, 0]                       # pasos seguidos en +3 / -3 del actuador del modo
        self.mostrado = [0.0] * N_CAN
        self.t = 0
        self.perturbacion = inicial.get('perturbacion')   # (paso, canal, cambio) en escenarios
        self.rng = random.Random(semilla_ruido)

    def clonar(self):
        c = copy.copy(self)
        c.h, c.d, c.racha, c.mostrado = list(self.h), list(self.d), list(self.racha), list(self.mostrado)
        c.historial = [list(u) for u in self.historial]
        c.rng = random.Random()
        c.rng.setstate(self.rng.getstate())
        return c

    def _efectivas(self):
        u = [self.historial[-1 - self.e['retardo'][a]][a] for a in range(N_ACT)]
        m = self.e['modo']
        if m and self.modo == 1:
            u[m['invertido']] = -u[m['invertido']]          # el régimen siempre invierte un actuador
            if m['permutar']:
                u = u[::-1]
        return u

    def salida(self):
        """Salida verdadera (la que se evalúa)."""
        y = list(self.h)
        if self.e['histeresis']:
            y[self.e['histeresis']['canal']] += self.histe
        return y

    def paso(self, acciones):
        acciones = [max(-LIMITE, min(LIMITE, round(float(a), 2))) for a in acciones]
        self.historial = self.historial[1:] + [acciones]
        m = self.e['modo']
        if m:
            v = acciones[m['actuador']]
            self.racha = [self.racha[0] + 1 if v >= 2.9 else 0, self.racha[1] + 1 if v <= -2.9 else 0]
            if self.racha[0] >= m['pasos']:
                self.modo = 1
            elif self.racha[1] >= m['pasos']:
                self.modo = 0
        if self.perturbacion and self.t == self.perturbacion[0]:
            self.d[self.perturbacion[1]] += self.perturbacion[2]
        self.d = [d + dv for d, dv in zip(self.d, self.e['deriva'])]
        u = self._efectivas()
        for c in range(N_CAN):
            f = sum(self.e['G'][c][a] * u[a] for a in range(N_ACT)) + self.d[c]
            lam = self.e['lam'][c]
            self.h[c] = lam * self.h[c] + (1 - lam) * f
        hi = self.e['histeresis']
        if hi:
            h = self.h[hi['canal']]
            if h > hi['alto']:
                self.histe = hi['salto']
            elif h < hi['bajo']:
                self.histe = -hi['salto']
        self.t += 1
        return self.lecturas()

    def lecturas(self):
        y = self.salida()
        for c in range(N_CAN):
            if self.t % self.e['aliasing'][c] == 0:
                self.mostrado[c] = y[c]
        out = list(self.mostrado)
        s = self.e['saturacion']
        if s:
            out[s['canal']] = max(-s['limite'], min(s['limite'], out[s['canal']]))
        return [round(v + self.rng.gauss(0, self.e['ruido']), 3) for v in out]


def inicial_aleatorio(rng, espec, escenario=False):
    ini = {'h': [round(rng.uniform(-2, 2), 2) for _ in range(N_CAN)],
           'd': [round(rng.uniform(-0.8, 0.8), 2) for _ in range(N_CAN)],
           'modo': rng.randrange(2) if espec['modo'] else 0,
           'histe': rng.choice([-1, 1]) * espec['histeresis']['salto'] if espec['histeresis'] else 0.0}
    if escenario:
        ini['perturbacion'] = (rng.randrange(10, 25), rng.randrange(N_CAN), round(rng.choice([-1, 1]) * rng.uniform(0.4, 1.0), 2))
    return ini


# --------------------------------------------------------------------------------------------------- problema

def construir(semilla, tipos):
    """Problema completo (con la verdad oculta). Lo visible para el resolutor sale de `visible`."""
    rng = random.Random(f'maquina-{semilla}')
    objetivo = [round(rng.uniform(-1.5, 1.5), 2) for _ in range(N_CAN)]
    espec = especificar(rng, tipos, objetivo)
    exploracion = inicial_aleatorio(rng, espec)
    escenarios = [inicial_aleatorio(random.Random(f'esc-{semilla}-{k}'), espec, escenario=True)
                  for k in range(N_ESCENARIOS)]
    return {'semilla': semilla, 'espec': espec, 'objetivo': objetivo, 'tol': espec['tol'],
            'exploracion': exploracion, 'escenarios': escenarios}


def visible(prob):
    """Lo único que recibe el resolutor: interfaz, objetivo y presupuesto. Ni tipos ni catálogo."""
    return {'actuadores': N_ACT, 'limite': LIMITE, 'canales': N_CAN, 'objetivo': prob['objetivo'],
            'tolerancia': prob['tol'], 'pasos_escenario': PASOS_ESCENARIO, 'ventana': VENTANA,
            'cumple': CUMPLE, 'presupuesto_pasos': PRESUPUESTO_PASOS}


def maquina_exploracion(prob):
    return Maquina(prob['espec'], prob['exploracion'], f'ruido-exp-{prob["semilla"]}')


def evaluar(prob, controlador):
    """controlador(lecturas, memoria) -> acciones. Fracción de escenarios retenidos cumplidos (por código)."""
    cumplidos = []
    for k, ini in enumerate(prob['escenarios']):
        m = Maquina(prob['espec'], ini, f'ruido-esc-{prob["semilla"]}-{k}')
        cumplidos.append(_cumple(prob, m, lambda lec, mem, m=m: controlador(lec, mem)))
    return sum(cumplidos) / len(cumplidos)


def _cumple(prob, m, decidir):
    memoria, lec, dentro = {}, m.lecturas(), 0
    for t in range(PASOS_ESCENARIO):
        lec = m.paso(decidir(lec, memoria))
        if t >= PASOS_ESCENARIO - VENTANA and all(abs(y - o) <= prob['tol'] for y, o in zip(m.salida(), prob['objetivo'])):
            dentro += 1
    return dentro / VENTANA >= CUMPLE


# --------------------------------------------------------------------------------------------------- referencias

def _coste(prob, y):
    return sum(max(0.0, abs(v - o) - prob['tol'] * 0.5) for v, o in zip(y, prob['objetivo']))


def ideal(prob):
    """Con acceso privilegiado (clona la máquina): cada paso prueba cada acción mantenida un horizonte."""
    H = max(prob['espec']['retardo']) + 4
    puntos = 0
    for k, ini in enumerate(prob['escenarios']):
        m = Maquina(prob['espec'], ini, f'ruido-esc-{prob["semilla"]}-{k}')

        def decidir(lec, mem, m=m):
            def coste(u):
                c, total = m.clonar(), 0.0
                hi = prob['espec']['histeresis']
                for _ in range(H):
                    c.paso(u)
                    # conocimiento del mecanismo (acceso privilegiado): la rama estable de la histéresis es la alta
                    total += _coste(prob, c.salida()) + (3.0 if hi and c.histe != hi['salto'] else 0.0)
                return total
            return buscar(coste)
        puntos += _cumple(prob, m, decidir)
    return puntos / len(prob['escenarios'])


def buscar(coste):
    """Rejilla gruesa (pasos de 1) y refinado alrededor del mejor (pasos de 0,25)."""
    mejor = min(COMBOS, key=coste)
    finos = [tuple(max(-LIMITE, min(LIMITE, b + 0.25 * k)) for b, k in zip(mejor, ks))
             for ks in itertools.product((-2, -1, 0, 1, 2), repeat=N_ACT)]
    return list(min(finos, key=coste))


def ingenuo(prob):
    """Método convencional sin memoria: estima la ganancia con un toque por actuador y corrige con realimentación."""
    m = maquina_exploracion(prob)
    base = m.paso([0] * N_ACT)
    Gh = []
    for a in range(N_ACT):
        u = [0] * N_ACT
        u[a] = 1
        Gh.append([y - b for y, b in zip(m.paso(u), base)])
        m.paso([0] * N_ACT)
    Gh = np.array(Gh).T

    def controlador(lec, mem):
        u_prev = np.array(mem.get('u', [0] * N_ACT))
        sesgo = np.array(lec) - Gh @ u_prev
        u, *_ = np.linalg.lstsq(Gh, np.array(prob['objetivo']) - sesgo, rcond=None)
        u = [max(-LIMITE, min(LIMITE, float(v))) for v in u]
        mem['u'] = u
        return u
    return evaluar(prob, controlador)


def generico(prob, retardos=4):
    """Identificación lineal genérica: excitación aleatoria con todo el presupuesto, modelo ARX ajustado por mínimos
    cuadrados y control predictivo con él."""
    rng = random.Random(f'generico-{prob["semilla"]}')
    m = maquina_exploracion(prob)
    us, ys = [], [m.lecturas()]
    for _ in range(PRESUPUESTO_PASOS):
        u = [round(rng.uniform(-LIMITE, LIMITE), 2) for _ in range(N_ACT)]
        us.append(u)
        ys.append(m.paso(u))
    L = retardos
    X, Y = [], []
    for t in range(L, len(us)):
        X.append(_regresor(ys, us, t, L))
        Y.append(ys[t + 1])
    coef, *_ = np.linalg.lstsq(np.array(X), np.array(Y), rcond=None)
    H = L + 3

    def controlador(lec, mem):
        hy = mem.setdefault('y', [lec] * (L + 1))
        hu = mem.setdefault('u', [[0] * N_ACT] * (L + 1))
        # desviación estimada por realimentación (control predictivo estándar): lectura menos lo que se predijo
        desvio = np.array(lec) - mem['prevista'] if 'prevista' in mem else np.zeros(N_CAN)
        hy.append(lec)

        def prever(u):
            py, pu, ys_ = list(hy), list(hu), []
            for _ in range(H):
                pu = pu + [list(u)]
                y = np.array(_regresor(py, pu, len(pu) - 1, L)) @ coef
                py = py + [list(y)]
                ys_.append(y)
            return ys_
        mejor = buscar(lambda u: sum(_coste(prob, y + desvio) for y in prever(u)))
        mem['prevista'] = prever(mejor)[0]
        hu.append(list(mejor))
        del hy[:-(L + 1)], hu[:-(L + 1)]
        return list(mejor)
    return evaluar(prob, controlador)


def _regresor(ys, us, t, L):
    fila = [1.0]
    for l in range(L + 1):
        fila += list(ys[t - l]) + list(us[t - l])
    return fila


# --------------------------------------------------------------------------------------------------- secuencias

NO_LINEALES = ('histeresis', 'modo', 'aliasing', 'saturacion')   # los que no resuelve el método genérico
LINEALES = ('retardo', 'acumulador', 'deriva')                   # los resuelve; van como acompañantes


def calibrar(prob):
    """Puntuaciones de referencia y estrato (lo usa el generador y queda en el banco)."""
    r = {'ideal': ideal(prob), 'ingenuo': ingenuo(prob), 'generico': generico(prob)}
    r['estrato'] = 'facil' if max(r['ingenuo'], r['generico']) >= UMBRAL_FACIL else 'dificil'
    return r


def secuencia(semilla, n_construccion=8, n_afines=6, n_ajenos=2, recurrentes=2, p_facil=0.25, intentos=80):
    """Una secuencia: dos tipos no lineales recurrentes propios, problemas de construcción y de prueba (afines: tipos
    recurrentes en combinaciones nuevas; ajenos: tipos no lineales que la secuencia no usa). Los lineales van como
    acompañantes y una parte de los problemas solo los lleva a ellos (fáciles, dueño). Solo se aceptan problemas que
    el ideal resuelve."""
    rng = random.Random(f'secuencia-{semilla}')
    propios = rng.sample(NO_LINEALES, recurrentes)
    ajenos_t = [t for t in NO_LINEALES if t not in propios]
    salida = {'semilla': semilla, 'recurrentes': propios, 'construccion': [], 'afines': [], 'ajenos': []}
    n = 0
    for clase, cuantos in (('construccion', n_construccion), ('afines', n_afines), ('ajenos', n_ajenos)):
        # estrato fijado por posición antes de generar (decidirlo en cada intento sesga hacia los fáciles)
        faciles = set(rng.sample(range(cuantos), round(p_facil * cuantos))) if clase != 'ajenos' else set()
        while len(salida[clase]) < cuantos:
            n += 1
            if n > intentos * (n_construccion + n_afines + n_ajenos):
                raise RuntimeError(f'secuencia {semilla}: no salen problemas resolubles')
            acompanante = [rng.choice(LINEALES)] if rng.random() < 0.5 else []
            facil = len(salida[clase]) in faciles
            if facil:
                tipos = acompanante
            elif clase == 'ajenos':
                tipos = rng.sample(ajenos_t, rng.randint(1, len(ajenos_t))) + acompanante
            else:
                tipos = rng.sample(propios, rng.randint(1, len(propios))) + acompanante
            ps = f'{semilla}-{n}'
            prob = construir(ps, tipos)
            cal = calibrar(prob)
            # cuota por estrato: sin ella, el filtro del ideal (que falla más en los difíciles) sesga hacia los fáciles
            if cal['ideal'] < UMBRAL_IDEAL or cal['estrato'] != ('facil' if facil else 'dificil'):
                continue
            salida[clase].append({'semilla': ps, 'tipos': sorted(tipos), **cal})
    return salida
