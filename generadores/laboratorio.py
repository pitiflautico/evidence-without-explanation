"""Laboratorio de organización (notas/diseno-organizacion.md §1). Sin IA.

Un sistema sintético de subsistemas → componentes → parámetros con 4 niveles ordenados. Las reglas restringen los
niveles (mínimos, máximos, mínimos que dependen de otro parámetro). Toda regla está escrita en algún documento
vigente; las **visibles** se pueden comprobar con `ejecutar_prueba` y las **ocultas** solo las juzga la evaluación
final (regresiones que un lector atento de la documentación evita).

Cadenas de fallo:
- `trampa`: el mínimo visible (que depende de un compañero) deja pasar un nivel por debajo del correcto; un mínimo
  oculto, escrito en otro documento, exige el correcto; un máximo lo fija. Subir de nivel en nivel hasta que pase la
  prueba visible cae en la trampa.
- `acoplada`: dos fallos, cada uno con su trampa. El mínimo de p1 sale de una regla cruzada que depende del valor
  **nuevo** de p2 y está escrita en la documentación del otro lado. Arreglar cada parte por separado no basta.

Familias: integrada (una acoplada dentro de un solo subsistema, corpus pequeño), distribuida (tres trampas en tres
subsistemas independientes, muchos registros), interdependiente (una acoplada entre dos subsistemas y un tercero sin
fallo, corpus mediano).

El lector ideal resuelve con todas las reglas vigentes: la solución es el único conjunto de cambios mínimo que las
cumple. El generador añade reglas fijadoras (satisfechas por la verdad) hasta que esa solución es única y es la
verdadera.
"""
import itertools
import json
import random
import re
from collections import Counter

NIVELES = 4
FAMILIAS = ('integrada', 'distribuida', 'interdependiente')

SUBSISTEMAS = ['ingesta', 'pagos', 'catálogo', 'mensajería', 'informes', 'identidad', 'búsqueda', 'envíos']
COMPONENTES = ['cola', 'pasarela', 'almacén', 'indexador', 'planificador', 'caché', 'notificador', 'validador',
               'agregador', 'exportador', 'balanceador', 'sincronizador']
PARAMETROS = [('tiempo_espera', 'ms', [250, 500, 1000, 2000]), ('reintentos', '', [0, 1, 3, 5]),
              ('hilos', '', [2, 4, 8, 16]), ('lote', 'registros', [10, 50, 100, 500]),
              ('memoria', 'MB', [256, 512, 1024, 2048]), ('conexiones', '', [5, 10, 20, 40]),
              ('ttl', 's', [30, 60, 300, 900]), ('intervalo', 's', [5, 15, 60, 300]),
              ('cola_max', 'mensajes', [100, 500, 1000, 5000]), ('compresion', 'nivel', [0, 1, 3, 6])]
COMPORTAMIENTOS = [
    ('latencia de respuesta', ['respuestas lentas', 'tiempo de respuesta por encima del objetivo', 'peticiones que tardan']),
    ('pérdida de mensajes', ['mensajes descartados', 'eventos que no llegan', 'huecos en la secuencia']),
    ('uso de memoria', ['memoria al límite', 'el proceso reinicia por memoria', 'presión de memoria']),
    ('errores de conexión', ['conexiones rechazadas', 'no se puede abrir conexión', 'conexión cerrada por el remoto']),
    ('duplicados', ['registros repetidos', 'el mismo evento procesado dos veces', 'claves duplicadas']),
    ('caducidad de sesiones', ['sesiones que expiran antes de tiempo', 'usuarios desconectados', 'token caducado']),
    ('retraso de sincronización', ['réplicas desfasadas', 'datos atrasados respecto al origen', 'sincronía perdida']),
    ('saturación de la cola', ['cola llena', 'productores bloqueados', 'rechazo por capacidad']),
    ('consumo de CPU', ['CPU al máximo', 'hilos bloqueados en espera activa', 'carga sostenida']),
    ('tiempos de arranque', ['arranque lento', 'el servicio tarda en estar listo', 'comprobación de salud fallida']),
    ('cortes en exportaciones', ['ficheros incompletos', 'exportación interrumpida', 'lotes truncados']),
    ('fallos de autenticación', ['credenciales rechazadas', 'firma no válida', 'acceso denegado']),
    ('consultas vacías', ['resultados vacíos', 'índice sin datos', 'búsquedas que no devuelven nada']),
    ('reintentos en cascada', ['tormenta de reintentos', 'peticiones repetidas', 'amplificación de tráfico']),
    ('timeouts del balanceador', ['el balanceador corta la petición', 'pasarela agotada', '504 en el borde']),
    ('desbordamiento de lotes', ['lote demasiado grande', 'escritura parcial', 'límite de tamaño superado']),
]
# tamaño por familia: días de registro por subsistema, líneas por día, documentos de ruido
TAMANO = {'integrada': (4, 6, 4), 'distribuida': (22, 26, 12), 'interdependiente': (10, 14, 8)}
PRUEBAS = {'A': 4, 'otras': 12}


# ------------------------------------------------------------------------------------------------- reglas

def cumple(regla, conf):
    t, p = regla['tipo'], regla['p']
    if t == 'min':
        return conf[p] >= regla['k']
    if t == 'max':
        return conf[p] <= regla['k']
    return conf[p] >= regla['tabla'][conf[regla['q']]]          # 'cond': mínimo de p según el nivel de q


def fallan(reglas, conf):
    return [r for r in reglas if not cumple(r, conf)]


def soluciones(reglas, inicial, max_cambios=4):
    """Conjuntos de cambios de tamaño mínimo que cumplen todas las reglas (el lector ideal)."""
    params = sorted({r['p'] for r in reglas} | {r['q'] for r in reglas if r['tipo'] == 'cond'})
    if not fallan(reglas, inicial):
        return [{}]
    for k in range(1, max_cambios + 1):
        hallados = []
        for grupo in itertools.combinations(params, k):
            opciones = [[n for n in range(NIVELES) if n != inicial[p]] for p in grupo]
            for niveles in itertools.product(*opciones):
                conf = {**inicial, **dict(zip(grupo, niveles))}
                if not fallan(reglas, conf):
                    hallados.append(dict(zip(grupo, niveles)))
        if hallados:
            return hallados
    return []


# ------------------------------------------------------------------------------------------------- generación

class _Constructor:
    def __init__(self, familia, semilla):
        self.familia, self.rng = familia, random.Random(f'lab-{familia}-{semilla}')
        self.reglas, self.cadenas, self.params, self.unidad = [], [], {}, {}
        self.comportamientos = list(COMPORTAMIENTOS)
        self.rng.shuffle(self.comportamientos)

    def subsistemas(self, n, componentes=2, por_componente=3):
        nombres = self.rng.sample(SUBSISTEMAS, n)
        comps = self.rng.sample(COMPONENTES, n * componentes)
        estructura = {}
        for i, s in enumerate(nombres):
            estructura[s] = {}
            for c in comps[i * componentes:(i + 1) * componentes]:
                for nombre, unidad, valores in self.rng.sample(PARAMETROS, por_componente):
                    clave = f'{c}.{nombre}'
                    estructura[s].setdefault(c, []).append(clave)
                    self.params[clave] = {'subsistema': s, 'componente': c, 'unidad': unidad, 'valores': valores}
        self.estructura = estructura
        return nombres

    def comportamiento(self):
        # sin repetir mientras queden; después se repiten (el nombre de la comprobación lleva el componente)
        return self.comportamientos.pop() if self.comportamientos else self.rng.choice(COMPORTAMIENTOS)

    def regla(self, tipo, p, visible, sitio, q=None, k=None, tabla=None, papel=''):
        r = {'id': f'R{len(self.reglas) + 1:02d}', 'tipo': tipo, 'p': p, 'visible': visible, 'sitio': sitio,
             'papel': papel, 'comportamiento': self.comportamiento()}
        if tipo == 'cond':
            r.update(q=q, tabla=tabla)
        else:
            r['k'] = k
        self.reglas.append(r)
        return r

    def params_de(self, subsistema):
        return [p for c in self.estructura[subsistema].values() for p in c]


def _tabla_monotona(rng, nivel_q, valor_en_q):
    """Mínimo de p para cada nivel de q, no decreciente, con tabla[nivel_q] = valor_en_q."""
    tabla = [0] * NIVELES
    tabla[nivel_q] = valor_en_q
    for n in range(nivel_q - 1, -1, -1):
        tabla[n] = max(0, tabla[n + 1] - rng.choice([0, 1]))
    for n in range(nivel_q + 1, NIVELES):
        tabla[n] = min(NIVELES - 1, tabla[n - 1] + rng.choice([0, 1]))
    return tabla


def _cadena_trampa(b, verdad, inicial, sub):
    """Fallo p con mínimo visible (según un compañero q) un nivel por debajo del correcto, mínimo oculto en otro
    documento y máximo que lo fija."""
    ps = b.params_de(sub)
    p, q = b.rng.sample(ps, 2)
    verdad[p] = b.rng.choice([2, 3])
    inicial[p] = b.rng.randrange(0, verdad[p] - 1)
    b.regla('cond', p, True, ('manual', p), q=q, tabla=_tabla_monotona(b.rng, verdad[q], verdad[p] - 1), papel='visible')
    otro = b.rng.choice([x for x in ps if x.split('.')[0] != p.split('.')[0]] or [q])
    b.regla('min', p, False, ('guia', otro.split('.')[0]), k=verdad[p], papel='oculta')
    if verdad[p] < NIVELES - 1:
        b.regla('max', p, b.rng.random() < .5, ('manual', p), k=verdad[p], papel='tope')
    b.cadenas.append({'tipo': 'trampa', 'fallos': [p], 'subsistemas': [sub], 'trampas': {p: verdad[p] - 1}})


def _cadena_acoplada(b, verdad, inicial, sub1, sub2):
    """p1 (en sub1) con mínimo visible un nivel bajo; la regla cruzada, escrita en sub2, exige más según el valor
    nuevo de p2 (en sub2), que también falla."""
    a = b.params_de(sub1)
    p1, q1 = b.rng.sample(a, 2)
    p2 = b.rng.choice([x for x in b.params_de(sub2) if x not in (p1, q1)])
    verdad[p1] = b.rng.choice([2, 3])
    inicial[p1] = b.rng.randrange(0, verdad[p1] - 1)
    verdad[p2] = b.rng.choice([2, 3])
    inicial[p2] = b.rng.randrange(0, verdad[p2] - 1)
    b.regla('cond', p1, True, ('manual', p1), q=q1, tabla=_tabla_monotona(b.rng, verdad[q1], verdad[p1] - 1), papel='visible')
    tabla = [0] * NIVELES                       # el valor correcto aparece una sola vez (en el nivel verdadero de p2)
    for n in range(NIVELES):
        tabla[n] = (min(NIVELES - 1, verdad[p1] + (n - verdad[p2])) if n >= verdad[p2]
                    else max(0, verdad[p1] - 1 - (verdad[p2] - 1 - n > 0)))
    b.regla('cond', p1, False, ('guia', p2.split('.')[0]), q=p2, tabla=tabla, papel='cruzada')
    b.regla('min', p2, True, ('manual', p2), k=verdad[p2] - 1, papel='visible')       # p2 también tiene trampa
    otro = b.rng.choice([x for x in b.params_de(sub2) if x.split('.')[0] != p2.split('.')[0]] or [p2])
    b.regla('min', p2, False, ('guia', otro.split('.')[0]), k=verdad[p2], papel='oculta')
    if verdad[p1] < NIVELES - 1:
        b.regla('max', p1, b.rng.random() < .5, ('manual', p1), k=verdad[p1], papel='tope')
    if verdad[p2] < NIVELES - 1:
        b.regla('max', p2, b.rng.random() < .5, ('manual', p2), k=verdad[p2], papel='tope')
    b.cadenas.append({'tipo': 'acoplada', 'fallos': [p1, p2], 'subsistemas': [sub1, sub2],
                      'trampas': {p1: verdad[p1] - 1, p2: verdad[p2] - 1}})


def _fijar(b, verdad, inicial, max_reglas=40):
    """Añade reglas satisfechas por la verdad hasta que la única solución mínima sea la verdadera."""
    objetivo = {p: verdad[p] for p in verdad if verdad[p] != inicial[p]}
    while len(b.reglas) < max_reglas:
        sols = soluciones(b.reglas, inicial, max_cambios=len(objetivo) + 1)
        if sols == [objetivo]:
            return True
        alternativa = next(s for s in sols if s != objetivo) if sols else None
        if alternativa is None:
            return False
        p = b.rng.choice([x for x in alternativa if alternativa[x] != verdad[x]])
        tipo = 'max' if alternativa[p] > verdad[p] else 'min'
        sitio = ('manual', p) if b.rng.random() < .6 else ('guia', b.rng.choice(sorted(b.params)).split('.')[0])
        de_cadena = any(p in c['fallos'] for c in b.cadenas)       # sobre un fallo, oculta: no anula la trampa
        b.regla(tipo, p, not de_cadena and b.rng.random() < .5, sitio, k=verdad[p], papel='fijadora')
    return False


def _reglas_extra(b, verdad, n):
    """Reglas que la verdad cumple y la configuración inicial también (contexto realista, sin fallo)."""
    libres = [p for p in b.params if not any(p in c['fallos'] for c in b.cadenas)]
    for p in b.rng.sample(libres, min(n, len(libres))):
        if verdad[p] > 0 and b.rng.random() < .5:
            b.regla('min', p, b.rng.random() < .6, ('manual', p), k=b.rng.randrange(0, verdad[p] + 1), papel='contexto')
        else:
            b.regla('max', p, b.rng.random() < .6, ('manual', p), k=b.rng.randrange(verdad[p], NIVELES), papel='contexto')


def construir(familia, semilla):
    """Estructura lógica del problema (sin textos). Reintenta con subsemillas hasta cumplir las condiciones."""
    for intento in range(200):
        b = _Constructor(familia, f'{semilla}-{intento}')
        if familia == 'integrada':
            subs = b.subsistemas(1, componentes=2)
        elif familia == 'distribuida':
            subs = b.subsistemas(3, componentes=2)
        else:
            subs = b.subsistemas(3, componentes=2)
        verdad = {p: b.rng.randrange(NIVELES) for p in b.params}
        inicial = dict(verdad)
        if familia == 'integrada':
            _cadena_acoplada(b, verdad, inicial, subs[0], subs[0])
        elif familia == 'distribuida':
            for s in subs:
                _cadena_trampa(b, verdad, inicial, s)
        else:
            _cadena_acoplada(b, verdad, inicial, subs[0], subs[1])
        _reglas_extra(b, verdad, {'integrada': 3, 'distribuida': 9, 'interdependiente': 6}[familia])
        if any(not cumple(r, verdad) for r in b.reglas):
            continue
        if not _fijar(b, verdad, inicial):
            continue
        prob = {'familia': familia, 'semilla': semilla, 'intento': intento, 'subsistemas': subs,
                'estructura': b.estructura, 'params': b.params, 'verdad': verdad, 'inicial': inicial,
                'reglas': b.reglas, 'cadenas': b.cadenas}
        if not validar_logica(prob):
            prob['documentos'] = _documentos(b, prob)
            if not superficial_resuelve(prob):      # ningún problema del banco lo resuelve un procedimiento superficial
                return prob
    raise RuntimeError(f'no se pudo construir {familia} {semilla}')


def objetivo(prob):
    return {p: prob['verdad'][p] for p in prob['verdad'] if prob['verdad'][p] != prob['inicial'][p]}


def validar_logica(prob):
    """Lista de problemas lógicos: solución única y verdadera, cada fallo visible, trampa real."""
    errores = []
    reglas, ini, ver = prob['reglas'], prob['inicial'], prob['verdad']
    if soluciones(reglas, ini, max_cambios=len(objetivo(prob)) + 1) != [objetivo(prob)]:
        errores.append('la solución mínima no es única o no es la verdadera')
    visibles = [r for r in reglas if r['visible']]
    if not fallan(visibles, ini):
        errores.append('ninguna prueba visible falla al principio')
    for c in prob['cadenas']:
        for p, t in c['trampas'].items():
            conf = {**ver, p: t}
            if fallan(visibles, conf) or not fallan(reglas, conf):
                errores.append(f'la trampa de {p} no es real')
    if prob['familia'] == 'interdependiente':
        if _local_acierta(prob):
            errores.append('el subsistema de p1, solo con sus documentos, ya da el valor correcto de p1')
        if not fallan(reglas, {**ini, **resolver_por_subsistema(prob)}):
            errores.append('resolver cada subsistema por separado y unirlo basta')
    return errores


def _local(prob, s):
    """Cambio mínimo y más cercano usando solo las reglas escritas en los documentos del subsistema s."""
    mias = [r for r in prob['reglas'] if _sub_del_sitio(prob, r['sitio']) == s]
    if not fallan(mias, prob['inicial']):
        return {}
    sols = soluciones(mias, prob['inicial'], max_cambios=3)
    ini = prob['inicial']
    return min(sols, key=lambda c: sum(abs(v - ini[p]) for p, v in c.items())) if sols else {}


def _local_acierta(prob):
    """En la acoplada entre subsistemas, ¿quien solo mira el subsistema de p1 acierta p1? No debe: la regla que lo
    decide está escrita al otro lado y depende del valor nuevo de p2."""
    c = prob['cadenas'][0]
    p1 = c['fallos'][0]
    return _local(prob, c['subsistemas'][0]).get(p1, prob['inicial'][p1]) == prob['verdad'][p1]


def _sub_del_sitio(prob, sitio):
    tipo, x = sitio
    comp = x.split('.')[0]
    return next(p['subsistema'] for p in prob['params'].values() if p['componente'] == comp)


# ------------------------------------------------------------------------------------------------- textos

def valor(prob, p, nivel):
    m = prob['params'][p]
    return f'{m["valores"][nivel]}{(" " + m["unidad"]) if m["unidad"] else ""}'


def _texto_regla(rng, prob, r, tabla=None):
    p = r['p']
    comp = r['comportamiento'][0]
    tabla = tabla or r.get('tabla')
    if r['tipo'] == 'cond':
        partes = '; '.join(f'con {r["q"]} = {valor(prob, r["q"], n)}, al menos {valor(prob, p, tabla[n])}'
                           for n in range(NIVELES))
        return rng.choice([
            f'El mínimo de {p} depende de {r["q"]}: {partes}. Por debajo aparecen problemas de {comp}.',
            f'Ajuste de {p} según el valor de {r["q"]} ({partes}). Si se queda corto, se nota en {comp}.',
            f'Tabla de dimensionado: {partes}. Aplica a {p}; quedarse por debajo provoca {comp}.'])
    v = valor(prob, p, r['k'])
    if r['tipo'] == 'min':
        return rng.choice([
            f'{p} no puede bajar de {v}: por debajo hay {comp}, sobre todo después de un reinicio.',
            f'Mínimo operativo de {p}: {v}. Valores menores acaban en {comp}.',
            f'Recordatorio: con {p} por debajo de {v} se ha visto {comp} en producción.'])
    return rng.choice([
        f'{p} no debe superar {v}: por encima se produce {comp}.',
        f'Límite superior de {p}: {v}. Más alto provoca {comp}.',
        f'No subir {p} por encima de {v}; se ha comprobado que causa {comp}.'])


def _documentos(b, prob):
    rng = b.rng
    dias_reg, lineas, n_ruido = TAMANO[prob['familia']]
    docs = []

    def doc(tipo, dia, titulo, texto):
        docs.append({'tipo': tipo, 'dia': dia, 'titulo': titulo, 'texto': texto})

    # manuales y guías: reglas agrupadas por sitio
    por_sitio = {}
    for r in prob['reglas']:
        por_sitio.setdefault(tuple(r['sitio']), []).append(r)
    for (tipo, x), rs in por_sitio.items():
        if tipo == 'manual':
            titulo = f'Manual de {x.split(".")[0]}: {x.split(".")[1]} (revisión 3)'
        else:
            titulo = f'Guía de operación de {x} (revisión 3)'
        cuerpo = ' '.join(_texto_regla(rng, prob, r) for r in rs)
        dia = rng.randrange(20, 40)
        doc('manual' if tipo == 'manual' else 'guia', dia, titulo, cuerpo)
        for r in rs:                                         # versión antigua que contradice (reglas de las cadenas)
            if r['papel'] in ('visible', 'cruzada', 'oculta') and rng.random() < .7:
                vieja = dict(r)
                if r['tipo'] == 'cond':
                    tabla = [max(0, t - 1) for t in r['tabla']]
                    texto = _texto_regla(rng, prob, vieja, tabla)
                else:
                    vieja['k'] = max(0, r['k'] - 1) if r['tipo'] == 'min' else min(NIVELES - 1, r['k'] + 1)
                    texto = _texto_regla(rng, prob, vieja)
                doc(docs[-1]['tipo'], rng.randrange(1, 15), titulo.replace('revisión 3', 'revisión 2'), texto)
    # historial: el cambio que introdujo cada fallo y cambios señuelo
    dia_fallo = {}
    for c in prob['cadenas']:
        for p in c['fallos']:
            dia_fallo[p] = rng.randrange(42, 50)
            doc('historial', dia_fallo[p], f'Cambio de configuración en {p.split(".")[0]}',
                f'Se cambia {p} de {valor(prob, p, prob["verdad"][p])} a {valor(prob, p, prob["inicial"][p])}. '
                f'Motivo: {rng.choice(["reducir costes", "ajuste tras la migración", "petición del equipo", "prueba de rendimiento"])}.')
    for p in rng.sample(sorted(prob['params']), min(len(prob['params']), 2 + n_ruido // 3)):
        if p in dia_fallo:
            continue
        n = prob['verdad'][p]
        otro = (n + 1) % NIVELES
        d = rng.randrange(30, 50)
        doc('historial', d, f'Cambio de configuración en {p.split(".")[0]}',
            f'Se cambia {p} de {valor(prob, p, n)} a {valor(prob, p, otro)}. Motivo: prueba puntual.')
        doc('historial', d + 1, f'Reversión en {p.split(".")[0]}',
            f'Se revierte el cambio de ayer: {p} vuelve a {valor(prob, p, n)}.')
    # registros diarios por subsistema: errores de las pruebas visibles que fallan, el resto ruido
    visibles_fallan = [r for r in fallan([r for r in prob['reglas'] if r['visible']], prob['inicial'])]
    for s in prob['subsistemas']:
        comps = list(prob['estructura'][s])
        mias = [r for r in visibles_fallan if prob['params'][r['p']]['subsistema'] == s]
        for d in range(50, 50 + dias_reg):
            ls = []
            for _ in range(lineas):
                c = rng.choice(comps)
                if mias and rng.random() < .15:
                    r = rng.choice(mias)
                    ls.append(f'ERROR [{prob["params"][r["p"]]["componente"]}] {rng.choice(r["comportamiento"][1])} '
                              f'(petición {rng.randrange(10000, 99999)})')
                else:
                    ls.append(rng.choice([f'INFO [{c}] ciclo completado en {rng.randrange(20, 900)} ms',
                                          f'INFO [{c}] {rng.randrange(1, 500)} elementos procesados',
                                          f'WARN [{c}] latencia puntual de {rng.randrange(900, 3000)} ms',
                                          f'INFO [{c}] comprobación de salud correcta',
                                          f'DEBUG [{c}] caché renovada']))
            doc('registro', d, f'Registro de {s}, día {d}', '\n'.join(ls))
    for i in range(n_ruido):
        doc('ruido', rng.randrange(1, 60), rng.choice(['Acta de la reunión semanal', 'Plan de vacaciones',
                                                       'Inventario de equipos', 'Nota sobre la cafetería',
                                                       'Calendario de formación']),
            rng.choice(['Sin acuerdos relevantes para operaciones.', 'Se revisa el calendario del trimestre.',
                        'Pendiente de confirmar fechas.', 'Se pide actualizar el inventario antes de fin de mes.']))
    rng.shuffle(docs)
    for i, d in enumerate(sorted(docs, key=lambda d: d['dia'])):
        d['id'] = f'D{i + 1:03d}'
    return sorted(docs, key=lambda d: d['id'])


# ------------------------------------------------------------------------------------------------- evaluación

def probar(prob, cambios, visibles=True):
    """Comprobaciones con los cambios aplicados: {'pasan': n, 'fallan': [nombres]} (solo visibles, por defecto)."""
    conf = {**prob['inicial'], **cambios}
    rs = [r for r in prob['reglas'] if r['visible'] or not visibles]
    malas = fallan(rs, conf)
    return {'pasan': len(rs) - len(malas),
            'fallan': [f'{prob["params"][r["p"]]["componente"]}: {r["comportamiento"][0]}' for r in malas]}


def evaluar(prob, cambios):
    """Resultado final (visibles y ocultas). `cambios`: {parámetro: nivel}."""
    cambios = {p: v for p, v in (cambios or {}).items() if p in prob['params']}
    conf = {**prob['inicial'], **cambios}
    obj = objetivo(prob)
    antes = {r['id'] for r in fallan(prob['reglas'], prob['inicial'])}
    despues = fallan(prob['reglas'], conf)
    return {'resuelto': not despues, 'fallos_arreglados': sum(conf[p] == v for p, v in obj.items()),
            'fallos': len(obj), 'regresiones': sum(r['id'] not in antes for r in despues),
            'innecesarios': sum(1 for p in cambios if p not in obj and cambios[p] != prob['inicial'][p]),
            'reglas_que_fallan': len(despues)}


def nivel_de(prob, p, texto):
    """Nivel de un valor escrito («1000 ms», «1000») para el parámetro p, o None."""
    m = re.search(r'-?\d+', str(texto))
    if not m:
        return None
    v = int(m.group())
    vals = prob['params'][p]['valores']
    return vals.index(v) if v in vals else None


# ------------------------------------------------------------------------------------------------- procedimientos superficiales

_PALABRA = re.compile(r'[a-záéíóúñü_.]{3,}', re.I)


def _palabras(t):
    return set(w.lower() for w in _PALABRA.findall(t))


def _param_por_palabras(prob, sintoma):
    """El parámetro mencionado en el manual vigente que más palabras comparte con el síntoma."""
    vigentes = [d for d in prob['documentos'] if d['tipo'] in ('manual', 'guia') and 'revisión 3' in d['titulo']]
    w = _palabras(sintoma)
    mejor = max(vigentes, key=lambda d: len(w & _palabras(d['texto'])))
    citados = [p for p in prob['params'] if p in mejor['texto']]
    return citados


def _valor_mas_citado(prob, p):
    c = Counter()
    for d in prob['documentos']:
        if d['tipo'] in ('manual', 'guia'):
            for m in re.finditer(re.escape(p) + r'[^.;]*?(-?\d+)', d['texto']):
                n = nivel_de(prob, p, m.group(1))
                if n is not None:
                    c[n] += 1
    return c.most_common(1)[0][0] if c else None


def m1_palabras(prob):
    cambios = {}
    for nombre in probar(prob, {})['fallan']:
        for p in _param_por_palabras(prob, nombre)[:1]:
            n = _valor_mas_citado(prob, p)
            if n is not None and n != prob['inicial'][p]:
                cambios[p] = n
    return cambios


def m2_ensayo(prob, ejecuciones=PRUEBAS['otras']):
    """Subir o bajar de nivel en nivel los parámetros citados junto a cada síntoma, aceptando lo que reduzca los
    fallos visibles, con el mismo número de ejecuciones que tiene el sistema."""
    cambios, usadas = {}, 0
    actual = len(probar(prob, {})['fallan'])
    while actual and usadas < ejecuciones:
        mejora = False
        for nombre in probar(prob, cambios)['fallan']:
            for p in _param_por_palabras(prob, nombre):
                base = cambios.get(p, prob['inicial'][p])
                for paso in (1, -1):
                    n = base + paso
                    if not 0 <= n < NIVELES or usadas >= ejecuciones:
                        continue
                    usadas += 1
                    prueba = {**cambios, p: n}
                    f = len(probar(prob, prueba)['fallan'])
                    if f < actual:
                        cambios, actual, mejora = prueba, f, True
                        break
                if mejora:
                    break
            if mejora:
                break
        if not mejora:
            break
    return cambios


def superficial_resuelve(prob):
    return evaluar(prob, m1_palabras(prob))['resuelto'] or evaluar(prob, m2_ensayo(prob))['resuelto']


def resolver_por_componente(prob):
    """Como resolver_por_subsistema, pero dividiendo por componente: cada parte solo con los documentos de su
    componente (manuales de sus parámetros y su guía)."""
    cambios = {}
    for comp in sorted({m['componente'] for m in prob['params'].values()}):
        mias = [r for r in prob['reglas'] if r['sitio'][1].split('.')[0] == comp]
        if fallan(mias, prob['inicial']):
            sols = soluciones(mias, prob['inicial'], max_cambios=3)
            if sols:
                ini = prob['inicial']
                for p, v in min(sols, key=lambda c: sum(abs(v - ini[p]) for p, v in c.items())).items():
                    if prob['params'][p]['componente'] == comp or p not in cambios:
                        cambios[p] = v
    return cambios


def resolver_por_subsistema(prob):
    """Comprobación 4: cada subsistema resuelto por separado con sus propios documentos y unido después. Ante dos
    propuestas para el mismo parámetro, gana la del subsistema al que pertenece el parámetro (lo natural al dividir
    por subsistema)."""
    propuestas = {s: _local(prob, s) for s in prob['subsistemas']}
    cambios = {}
    for s, c in propuestas.items():
        for p, v in c.items():
            if prob['params'][p]['subsistema'] == s or p not in cambios:
                cambios[p] = v
    return cambios


# ------------------------------------------------------------------------------------------------- visible

def visible(prob):
    """Lo que ven las ramas: documentos y configuración inicial con valores (no niveles). Nunca reglas ni verdad."""
    return {'familia': None, 'documentos': prob['documentos'],
            'configuracion': {p: valor(prob, p, n) for p, n in sorted(prob['inicial'].items())},
            'valores': {p: [f'{v}{(" " + m["unidad"]) if m["unidad"] else ""}' for v in m['valores']]
                        for p, m in sorted(prob['params'].items())}}


def caracteres(prob):
    return sum(len(d['titulo']) + len(d['texto']) for d in prob['documentos'])
