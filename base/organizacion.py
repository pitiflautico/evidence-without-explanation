"""Ramas del laboratorio de organización (notas/diseno-organizacion.md §2–3). Mismo modelo, mismas operaciones y
mismo tope de dólares por episodio; solo cambia cómo puede organizarse el trabajo.

| A | un contexto continuo, sin `abrir`; 40 turnos, 4 ejecuciones de prueba |
| A_ext | A con más oportunidades: 120 turnos, 12 ejecuciones y un aviso único si entrega con menos de la mitad gastada |
| B | flujo fijo de tres contextos nuevos en serie: investigar → ejecutar → revisar (12 ejecuciones en total) |
| A_igual | A con los recursos de X (12 pruebas, 120 turnos), sin abrir ni aviso (comparación A / X / X_cob) |
| X_cob | X y, tras cada prueba, cuántos documentos normativos vigentes de cada parámetro cambiado se han consultado |
| X | A más `abrir`: cualquier contexto puede abrir otros, anotar, terminar sin informe o entregar (120 turnos por
  contexto y 12 ejecuciones, como A_ext: sin abrir nada, X tiene los mismos recursos que su control) |

Ningún texto recomienda dividir ni no dividir. `entregar` termina el episodio desde cualquier contexto (excepción
`Entregado`, que atraviesa los bucles de todos los contextos abiertos).
"""
import math
import re
import time
from collections import Counter
from functools import partial

from ejecutor.agente import Herramienta, Presupuesto, correr
from generadores import laboratorio as L

# X: 120 por contexto, como A_ext (dueño 21/10): un X que no se divide no puede tener menos turnos que su control
TURNOS = {'A': 40, 'A_ext': 120, 'B': 40, 'X': 120}
MAX_CONTEXTOS = 12
AVISO_EXT = 0.5

SISTEMA = (
    'Tu responsabilidad es que un sistema informático vuelva a funcionar. Varias comprobaciones automáticas fallan. '
    'Dispones de la documentación del sistema (manuales, guías de operación, historial de cambios, registros y otros '
    'documentos) y de herramientas para consultarla, ver la configuración y ejecutar las comprobaciones con cambios '
    'candidatos. Objetivo: entregar el conjunto de cambios de configuración que hace pasar todas las comprobaciones, '
    'también las que no puedes ejecutar (la documentación describe todas las reglas que el sistema debe cumplir), sin '
    'cambios innecesarios. Si dos documentos se contradicen, manda la revisión más reciente. El presupuesto y las '
    'ejecuciones de prueba son limitados. Entrega con entregar; la entrega es definitiva.')

TEXTO_ABRIR = (
    ' También puedes abrir contextos nuevos e independientes con abrir: cada uno empieza sin tu conversación, recibe la '
    'pregunta, los documentos y, si quieres, el estado compartido que le pases, y tiene las mismas herramientas que tú '
    '(también abrir, mientras quede presupuesto). Un contexto puede anotar en el estado compartido, terminar con o sin '
    'resumen, o entregar la solución. Úsalo como te parezca útil, o no lo uses.')

ETAPAS_B = [
    ('investigar', 'Etapa 1 de 3 (investigar): averigua las causas de los fallos y anota en el estado compartido lo que '
                   'encuentres, con las referencias de los documentos. No entregues: termina con terminar cuando hayas '
                   'anotado lo necesario.'),
    ('ejecutar', 'Etapa 2 de 3 (ejecutar): a partir del estado compartido, propone los cambios, pruébalos y anota la '
                 'propuesta y los resultados. No entregues: termina con terminar.'),
    ('revisar', 'Etapa 3 de 3 (revisar): revisa la propuesta del estado compartido contra la documentación, comprueba lo '
                'que haga falta y entrega la solución final con entregar.'),
]


class Entregado(Exception):
    pass


def _palabras_v1(texto):
    """Buscador de la calibración, conservado (defecto: «componente.parametro» es una sola palabra, así que las
    consultas naturales como «componente parametro» no encuentran los documentos que solo lo nombran con el punto)."""
    return re.findall(r'[a-záéíóúñü0-9_.]{3,}', texto.lower())


def _palabras(texto):
    """Buscador v2 (auditoría 21/10): cada nombre compuesto cuenta entero y también por partes, separando por punto,
    guion y guion bajo. «agregador.cola_max» da agregador.cola_max, agregador, cola_max, cola y max."""
    salida = []
    for w in re.findall(r'[a-záéíóúñü0-9_.\-]+', texto.lower()):
        w = w.strip('._-')
        partes = {w} | set(re.split(r'[.\-]', w)) | set(re.split(r'[._\-]', w))
        salida += [x for x in partes if len(x) >= 3]
    return salida


BUSCADORES = {1: _palabras_v1, 2: _palabras}
_NORMATIVO = re.compile(r'no puede bajar|mínimo|al menos|no debe superar|límite|no subir|depende de|por debajo|'
                        r'por encima|tabla de dimensionado|ajuste de', re.I)
_REVISION = re.compile(r'\s*\(revisión (\d+)\)\s*$')


def pertinentes(documentos):
    """{parámetro: ids} de los documentos que lo regulan, calculado solo con lo visible y reproducible:
    1) tipo normativo (manual o guía); 2) solo la revisión más reciente de cada título (se descartan las antiguas);
    3) nombra el parámetro completo en una frase con lenguaje de regla (mínimo, al menos, no debe superar…), lo que
    descarta menciones de paso. No mira la solución ni sabe qué documento la contiene."""
    ultimo = {}
    for d in documentos:
        if d['tipo'] not in ('manual', 'guia'):
            continue
        m = _REVISION.search(d['titulo'])
        base, rev = (_REVISION.sub('', d['titulo']), int(m.group(1))) if m else (d['titulo'], 0)
        if base not in ultimo or (rev, d['dia']) > (ultimo[base][0], ultimo[base][1]['dia']):
            ultimo[base] = (rev, d)
    salida = {}
    for _, d in ultimo.values():
        for frase in re.split(r'(?<=\.)\s+', d['texto']):           # frases completas (el «;» no corta)
            if _NORMATIVO.search(frase):
                for nombre in set(re.findall(r'[a-záéíóúñü]+\.[a-záéíóúñü_]+', frase)):
                    salida.setdefault(nombre, set()).add(d['id'])
    return salida


class Mundo:
    """Estado de un episodio: documentos, búsqueda, ejecuciones de prueba, estado compartido y árbol de contextos."""

    def __init__(self, prob, presupuesto, pruebas, buscador=2, cobertura=False, revision=None):
        self.prob, self.presupuesto, self.pruebas_max = prob, presupuesto, pruebas
        self.vis = L.visible(prob)
        self.docs = {d['id']: d for d in self.vis['documentos']}
        self.pruebas, self.notas, self.contextos, self.solucion, self.lecturas = [], [], [], None, []
        self.mostrados, self.buscador, self.cobertura = [], buscador, []    # mostrados: (contexto, ids) por búsqueda
        self.consultas, self.revision = [], revision  # revisión: se activa tras leer y probar (base/necesidades.py)
        self._tokens = BUSCADORES[buscador]
        self._pertinentes = None
        if cobertura:                                 # coste de calcular la señal: se mide y se registra
            t0 = time.perf_counter()
            self._pertinentes = pertinentes(self.vis['documentos'])
            self.cobertura.append({'indice_segundos': round(time.perf_counter() - t0, 5)})
        tf = {i: Counter(self._tokens(d['titulo'] + ' ' + d['texto'])) for i, d in self.docs.items()}
        df = Counter(w for c in tf.values() for w in c)
        n = len(tf)
        self._vec = {i: {w: (1 + math.log(c)) * math.log(1 + n / df[w]) for w, c in t.items()} for i, t in tf.items()}

    # --- operaciones comunes
    def buscar(self, consulta, k=8, contexto=None):
        q = Counter(self._tokens(consulta))
        if self.buscador >= 2:                        # nombres compuestos escritos en dos palabras: «a b» → «a.b»…
            ws = re.findall(r'[a-záéíóúñü0-9_]+', consulta.lower())
            q.update(f'{a}{s}{b}' for a, b in zip(ws, ws[1:]) for s in '._-')
        puntos = sorted(((sum(v.get(w, 0) for w in q), i) for i, v in self._vec.items()), reverse=True)
        if contexto:                                  # qué llegó a la pantalla (separado de qué se leyó)
            self.mostrados.append((contexto, [i for s, i in puntos[:int(k)] if s > 0]))
            self.consultas.append((contexto, str(consulta)))
        filas = [f'{i} (día {self.docs[i]["dia"]}, {self.docs[i]["tipo"]}) {self.docs[i]["titulo"]}: '
                 f'{self.docs[i]["texto"][:100].replace(chr(10), " ")}…' for s, i in puntos[:int(k)] if s > 0]
        return '\n'.join(filas) or 'Sin resultados.'

    def leer(self, id, contexto=None):
        d = self.docs.get(str(id).strip())
        if d is None:
            raise ValueError(f'no existe el documento {id}')
        if contexto:                                  # quién leyó qué: conocimiento que se pierde al bifurcar
            self.lecturas.append((contexto, d['id']))
        return f'{d["id"]} · día {d["dia"]} · {d["tipo"]} · {d["titulo"]}\n{d["texto"]}'

    def configuracion(self):
        return '\n'.join(f'{p} = {v} (valores posibles: {", ".join(self.vis["valores"][p])})'
                         for p, v in self.vis['configuracion'].items())

    def _niveles(self, cambios):
        if not isinstance(cambios, dict) or not cambios:
            raise ValueError('cambios debe ser un objeto {parámetro: valor}')
        niveles = {}
        for p, v in cambios.items():
            if p not in self.prob['params']:
                raise ValueError(f'el parámetro {p} no existe')
            n = L.nivel_de(self.prob, p, v)
            if n is None:
                raise ValueError(f'{v} no es un valor posible de {p}: {", ".join(self.vis["valores"][p])}')
            niveles[p] = n
        return niveles

    def ejecutar_prueba(self, cambios, contexto):
        if len(self.pruebas) >= self.pruebas_max:
            raise ValueError(f'no quedan ejecuciones de prueba (usadas {len(self.pruebas)} de {self.pruebas_max})')
        niveles = self._niveles(cambios)
        r = L.probar(self.prob, niveles)
        self.pruebas.append({'contexto': contexto, 'cambios': niveles, 'fallan': len(r['fallan']),
                             'fallan_nombres': r['fallan']})
        quedan = self.pruebas_max - len(self.pruebas)
        return (f'{r["pasan"]} comprobaciones visibles pasan; fallan {len(r["fallan"])}'
                f'{": " + "; ".join(r["fallan"]) if r["fallan"] else ""}. Quedan {quedan} ejecuciones.'
                + self._cobertura(niveles, contexto))

    def _cobertura(self, niveles, contexto):
        """Solo X_cobertura: cuántos documentos que regulan cada parámetro cambiado se han consultado (leído, por
        cualquier contexto del episodio). Solo cuentas: ni ids ni contenido ni la respuesta."""
        if self._pertinentes is None:
            return ''
        t0 = time.perf_counter()
        leidos = {d for _, d in self.lecturas}
        filas, faltan = [], {}
        for p in sorted(niveles):
            todos = self._pertinentes.get(p, set())
            faltan[p] = len(todos - leidos)
            filas.append(f'{p}: {len(todos & leidos)} de {len(todos)}')
        self.cobertura.append({'contexto': contexto, 'faltan': faltan, 'segundos': round(time.perf_counter() - t0, 5)})
        return ('\nCobertura documental (calculada por código; no dice si la solución es correcta): documentos '
                'normativos vigentes que regulan cada parámetro cambiado, consultados de los que hay: ' + '; '.join(filas) + '.')

    def revisar(self, contexto):
        """Texto que añade la revisión de necesidades (DET o AUTO) tras una lectura o una prueba; vacío si no hay."""
        return self.revision(self, contexto) if self.revision else ''

    def anotar(self, texto, contexto, referencias=None):
        self.notas.append({'contexto': contexto, 'texto': str(texto), 'referencias': list(referencias or [])})
        return f'Nota {len(self.notas)} añadida al estado compartido.'

    def ver_estado(self):
        if not self.notas:
            return 'El estado compartido está vacío.'
        return '\n'.join(f'[{k + 1}, {n["contexto"]}] {n["texto"]}'
                         f'{" (refs: " + ", ".join(n["referencias"]) + ")" if n["referencias"] else ""}'
                         for k, n in enumerate(self.notas))

    def entregar(self, cambios, contexto):
        self.solucion = {'contexto': contexto, 'cambios': self._niveles(cambios) if cambios else {}}
        raise Entregado()

    def encargo(self):
        fallan = L.probar(self.prob, {})['fallan']
        return (f'Comprobaciones visibles que fallan ahora: {"; ".join(fallan)}.\n'
                f'Hay {len(self.docs)} documentos (consúltalos con buscar y leer). Presupuesto del episodio: '
                f'{self.presupuesto.maximo:.2f} $; ejecuciones de prueba disponibles: {self.pruebas_max}. '
                f'Los cambios se escriben con los valores tal como aparecen en la configuración, por ejemplo '
                f'{{"componente.parametro": "1000 ms"}}.')


ESQ_CAMBIOS = {'type': 'object', 'description': '{parámetro: valor}', 'additionalProperties': {'type': 'string'}}


def herramientas(m, contexto, abrir=None, terminar=False, entregar=None, extra=()):
    hs = [
        Herramienta('buscar', 'Documentos más parecidos a la consulta (id, día, tipo, título y comienzo).',
                    {'type': 'object', 'properties': {'consulta': {'type': 'string'}}, 'required': ['consulta']},
                    lambda consulta: m.buscar(consulta, contexto=contexto)),
        Herramienta('leer', 'Texto completo de un documento.',
                    {'type': 'object', 'properties': {'id': {'type': 'string'}}, 'required': ['id']},
                    lambda id: m.leer(id, contexto) + m.revisar(contexto)),
        Herramienta('configuracion', 'Configuración actual con los valores posibles de cada parámetro.',
                    {'type': 'object', 'properties': {}}, lambda: m.configuracion()),
        Herramienta('ejecutar_prueba', 'Ejecuta las comprobaciones visibles con esos cambios aplicados (no los deja '
                                       'aplicados). Consume una ejecución.',
                    {'type': 'object', 'properties': {'cambios': ESQ_CAMBIOS}, 'required': ['cambios']},
                    lambda cambios: m.ejecutar_prueba(cambios, contexto) + m.revisar(contexto)),
        Herramienta('anotar', 'Añade una nota al estado compartido.',
                    {'type': 'object', 'properties': {'texto': {'type': 'string'},
                                                      'referencias': {'type': 'array', 'items': {'type': 'string'}}},
                     'required': ['texto']},
                    lambda texto, referencias=None: m.anotar(texto, contexto, referencias)),
        Herramienta('ver_estado', 'Notas del estado compartido.', {'type': 'object', 'properties': {}},
                    lambda: m.ver_estado()),
        Herramienta('entregar', 'Entrega la solución final (definitiva): los cambios de configuración.',
                    {'type': 'object', 'properties': {'cambios': ESQ_CAMBIOS}, 'required': ['cambios']},
                    entregar or (lambda cambios: m.entregar(cambios, contexto)), terminal=True),
    ]
    hs += list(extra)
    if abrir:
        hs.append(Herramienta('abrir', 'Abre un contexto nuevo e independiente con esta pregunta, el texto de estos '
                                       'documentos y, si se pide, el estado compartido. Vuelve cuando ese contexto '
                                       'termina.',
                              {'type': 'object', 'properties': {
                                  'pregunta': {'type': 'string'},
                                  'documentos': {'type': 'array', 'items': {'type': 'string'}},
                                  'incluir_estado': {'type': 'boolean'},
                                  'presupuesto': {'type': 'number', 'description': 'tope en $ para ese contexto (opcional)'}},
                               'required': ['pregunta']}, abrir))
    if terminar:
        hs.append(Herramienta('terminar', 'Termina este contexto, con un resumen opcional para quien lo abrió.',
                              {'type': 'object', 'properties': {'resumen': {'type': 'string'}}},
                              lambda resumen='': 'Contexto terminado.', terminal=True))
    return hs


def _registrar(m, cid, padre, pregunta, documentos=(), incluir_estado=False):
    leidos_padre = sorted({d for c, d in m.lecturas if c == padre}) if padre else []
    m.contextos.append({'id': cid, 'padre': padre, 'pregunta': pregunta, 'documentos': list(documentos),
                        'leidos_por_padre_al_abrir': leidos_padre,
                        'incluir_estado': bool(incluir_estado), 'notas_al_abrir': len(m.notas),
                        'pruebas_al_abrir': len(m.pruebas), 'fin': None, 'turnos': 0})
    return m.contextos[-1]


def _cerrar(ctx, r, m):
    ctx['turnos'] = r['turnos'] if r else ctx['turnos']
    ctx['notas_aportadas'] = sum(1 for n in m.notas if n['contexto'] == ctx['id'])
    if r is not None and ctx['fin'] is None:
        ctx['fin'] = ('terminó' if r['terminal'] and r['terminal'][0] == 'terminar' else
                      'agotado' if r['agotado'] else 'sin entregar')
        if r['terminal'] and r['terminal'][0] == 'terminar':
            ctx['resumen'] = (r['terminal'][1] or {}).get('resumen', '')


# ------------------------------------------------------------------------------------------------------ ramas

def _episodio(m, ejecutar):
    try:
        ejecutar()
    except Entregado:
        pass
    for c in m.contextos:
        if c['fin'] is None and m.solucion and m.solucion['contexto'] == c['id']:
            c['fin'] = 'entregó'
        elif c['fin'] is None:
            c['fin'] = 'interrumpido por la entrega' if m.solucion else 'sin terminar'
        c['notas_aportadas'] = sum(1 for n in m.notas if n['contexto'] == c['id'])
    return {'solucion': m.solucion['cambios'] if m.solucion else None,
            'estructura': {'contextos': m.contextos, 'notas': m.notas, 'pruebas': m.pruebas, 'lecturas': m.lecturas,
                           'mostrados': m.mostrados, 'buscador': m.buscador, 'cobertura': m.cobertura,
                           'consultas': m.consultas,
                           'revisiones': getattr(m.revision, 'registro', []) if m.revision else [],
                           'pausas': getattr(m.revision, 'pausas', None) if m.revision else None,
                           'entregado_por': m.solucion['contexto'] if m.solucion else None}}


def rama_a(cliente, prob, presupuesto):
    m = Mundo(prob, presupuesto, L.PRUEBAS['A'])
    ctx = _registrar(m, 'A0', None, 'encargo')

    def ejecutar():
        r = correr(cliente, SISTEMA, m.encargo(), herramientas(m, 'A0'), presupuesto, 'A0', max_turnos=TURNOS['A'])
        _cerrar(ctx, r, m)
    return _episodio(m, ejecutar)


def rama_a_ext(cliente, prob, presupuesto):
    m = Mundo(prob, presupuesto, L.PRUEBAS['otras'])
    ctx = _registrar(m, 'E0', None, 'encargo')
    avisado = []

    def entregar(cambios):
        if not avisado and presupuesto.gastado < AVISO_EXT * presupuesto.maximo:
            avisado.append(len(presupuesto.llamadas))
            m._niveles(cambios)                       # valida el formato antes de avisar
            return ('Aún te queda más de la mitad del presupuesto. Puedes seguir investigando o probando; si estás '
                    'seguro, vuelve a llamar a entregar.')
        return m.entregar(cambios, 'E0')
    hs = herramientas(m, 'E0', entregar=entregar)
    hs[-1].terminal = False                           # el aviso no termina: la segunda llamada lanza Entregado

    def ejecutar():
        r = correr(cliente, SISTEMA, m.encargo(), hs, presupuesto, 'E0', max_turnos=TURNOS['A_ext'])
        _cerrar(ctx, r, m)
    salida = _episodio(m, ejecutar)
    salida['estructura']['aviso'] = avisado[0] if avisado else None
    return salida


def rama_b(cliente, prob, presupuesto):
    m = Mundo(prob, presupuesto, L.PRUEBAS['otras'])

    def ejecutar():
        for k, (nombre, texto) in enumerate(ETAPAS_B):
            cid = f'B{k}'
            ctx = _registrar(m, cid, f'B{k - 1}' if k else None, nombre, incluir_estado=k > 0)
            mensaje = m.encargo() + '\n\n' + texto + (f'\n\nEstado compartido:\n{m.ver_estado()}' if k else '')
            ultima = k == len(ETAPAS_B) - 1
            r = correr(cliente, SISTEMA, mensaje, herramientas(m, cid, terminar=not ultima, entregar=None if ultima
                                                               else _no_entregar), presupuesto, cid,
                       max_turnos=TURNOS['B'])
            _cerrar(ctx, r, m)
    return _episodio(m, ejecutar)


def _no_entregar(cambios):
    raise ValueError('en esta etapa no se entrega: anota y termina')


def rama_x(cliente, prob, presupuesto, cobertura=False, revision=None, extra=None):
    m = Mundo(prob, presupuesto, L.PRUEBAS['otras'], cobertura=cobertura, revision=revision)
    sistema = SISTEMA + TEXTO_ABRIR

    def contexto(cid, padre, mensaje, pregunta, pres_padre, documentos=(), incluir_estado=False, tope=None):
        """`pres_padre`: el presupuesto de quien lo abre. Con `tope`, el contexto lleva uno propio cuyo gasto se suma
        al del padre al terminar (así cuenta también para el tope del padre y para el del episodio)."""
        ctx = _registrar(m, cid, padre, pregunta, documentos, incluir_estado)
        mio = (Presupuesto(min(float(tope), pres_padre.restante()), modelo=pres_padre.modelo,
                           esfuerzo=pres_padre.esfuerzo) if tope is not None else pres_padre)
        t0 = time.monotonic()

        def abrir(pregunta, documentos=None, incluir_estado=False, presupuesto=None):
            if len(m.contextos) >= MAX_CONTEXTOS:
                raise ValueError(f'límite de {MAX_CONTEXTOS} contextos por episodio alcanzado')
            ids = [str(i) for i in (documentos or [])]
            faltan = [i for i in ids if i not in m.docs]
            if faltan:
                raise ValueError(f'documentos que no existen: {faltan}')
            hijo = f'X{len(m.contextos)}'
            partes = [f'Pregunta: {pregunta}']
            if ids:
                partes.append('Documentos:\n' + '\n\n'.join(m.leer(i) for i in ids))
            if incluir_estado:
                partes.append(f'Estado compartido:\n{m.ver_estado()}')
            partes.append(m.encargo())
            r = contexto(hijo, cid, '\n\n'.join(partes), pregunta, mio, ids, incluir_estado, presupuesto)
            nuevas = sum(1 for n in m.notas if n['contexto'] == hijo)
            resumen = (r['terminal'][1] or {}).get('resumen', '') if r and r['terminal'] else ''
            fin = next(c['fin'] for c in m.contextos if c['id'] == hijo)
            return (f'El contexto {hijo} terminó ({fin}). Notas nuevas en el estado: {nuevas}.'
                    + (f' Resumen: {resumen}' if resumen else ''))

        try:
            r = correr(cliente, sistema, mensaje, herramientas(m, cid, abrir=abrir, terminar=padre is not None,
                                                               extra=extra(m, cid) if extra else ()),
                       mio, cid, max_turnos=TURNOS['X'])
        finally:
            if mio is not pres_padre:
                pres_padre.gastado += mio.gastado
                pres_padre.llamadas += mio.llamadas
                pres_padre.interrupciones += mio.interrupciones
            ctx['segundos'] = round(time.monotonic() - t0, 2)
        _cerrar(ctx, r, m)
        return r

    return _episodio(m, lambda: contexto('X0', None, m.encargo(), 'encargo', presupuesto))


def rama_a_igual(cliente, prob, presupuesto, cobertura=False, revision=None, extra=None):
    """A con exactamente los recursos de X (12 pruebas, 120 turnos, mismo tope), sin abrir y sin aviso: lo que haría
    X si no se dividiera (dueño 21/10). Es la A de la comparación A / X / X_cobertura y la D de necesidades.
    `cobertura`, `revision` y `extra`: las variantes COB, DET y AUTO (base/necesidades.py)."""
    m = Mundo(prob, presupuesto, L.PRUEBAS['otras'], cobertura=cobertura, revision=revision)
    ctx = _registrar(m, 'A0', None, 'encargo')

    def ejecutar():
        r = correr(cliente, SISTEMA, m.encargo(), herramientas(m, 'A0', extra=extra(m, 'A0') if extra else ()),
                   presupuesto, 'A0', max_turnos=TURNOS['X'])
        _cerrar(ctx, r, m)
    return _episodio(m, ejecutar)


RAMAS_LAB = {'A': rama_a, 'A_ext': rama_a_ext, 'B': rama_b, 'X': rama_x, 'A_igual': rama_a_igual,
             'X_cob': partial(rama_x, cobertura=True)}
