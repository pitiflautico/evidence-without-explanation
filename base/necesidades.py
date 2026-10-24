"""Detección continua de necesidades (notas/diseno-necesidades.md). Laboratorio A: necesidades conocidas.

| D | A_igual: un contexto con los recursos de X |
| COB | D y la línea de cobertura por código tras cada prueba |
| DET | D y un detector (Haiku) que, tras cada lectura y cada prueba (como mucho 8 veces), hace explícitos hechos,
  hipótesis y necesidades (demostrables con ancla o hipotéticas); llega al resolutor como bloque pasivo |
| DET_X | X (puede abrir contextos) con el mismo detector |
| AUTO | D: en los mismos momentos y con la misma información (incluido el índice de documentos), se le pide al propio
  resolutor que registre el mismo formato; recibe el mismo bloque procesado |

El código no descarta nada (dueño): una necesidad «demostrable» cuyo ancla no existe se reclasifica como hipotética, y
un hecho sin apoyo existente se marca «sin apoyo verificado». El código solo comprueba que las referencias existen, no
que digan lo que se afirma. Un contador mecánico registra las frases que proponen valores o la solución (no bloquea).
"""
import re
from functools import partial

from ejecutor.agente import Herramienta, Presupuesto, correr

from . import organizacion as O

MODELO_DETECTOR = 'claude-haiku-5-5'
MAX_REVISIONES = 8

TEXTO_REVISION = (
    'Haz explícito el estado del conocimiento sobre el problema: qué se sabe y con qué apoyo, qué se está suponiendo '
    'y qué falta saber o comprobar. No resuelvas: no propongas valores ni la solución. Hay dos tipos de necesidad: '
    'demostrable (con ancla: id de documento, nombre de parámetro, número de prueba o contradicción entre documentos '
    'concretos) e hipotética (una sospecha que todavía no tiene ancla: una explicación, relación o posibilidad que '
    'quizá falta; di cómo se podría investigar). Las dos valen. Cada hecho, con su apoyo.')

SISTEMA_DETECTOR = (
    'Observas a otra instancia que intenta que un sistema informático vuelva a funcionar cambiando su configuración, '
    'con documentación (manuales, guías, historial, registros) y comprobaciones que puede ejecutar; hay '
    'comprobaciones que no puede ejecutar y que la documentación describe. Tú no actúas ni decides. '
    + TEXTO_REVISION + ' Entrega con entregar_estado.')

_ITEM = {'type': 'object', 'properties': {'texto': {'type': 'string'}, 'apoyo': {'type': 'array', 'items': {'type': 'string'}}},
         'required': ['texto']}
ESQUEMA_ESTADO = {'type': 'object', 'properties': {
    'hechos': {'type': 'array', 'items': _ITEM},
    'hipotesis': {'type': 'array', 'items': {'type': 'object', 'properties': {
        'texto': {'type': 'string'}, 'como_contrastar': {'type': 'string'}}, 'required': ['texto']}},
    'necesidades': {'type': 'array', 'items': {'type': 'object', 'properties': {
        'texto': {'type': 'string'}, 'tipo': {'type': 'string', 'enum': ['demostrable', 'hipotetica']},
        'ancla': {'type': 'array', 'items': {'type': 'string'}}, 'como_investigar': {'type': 'string'}},
        'required': ['texto', 'tipo']}}}, 'required': ['necesidades']}


def _anclas_validas(m, anclas):
    """Las referencias que existen: id de documento, parámetro, «prueba N» ya ejecutada."""
    validas = []
    for a in anclas or []:
        a = str(a).strip()
        n = re.fullmatch(r'(?:prueba\s*)?#?(\d+)', a, re.I)
        if a in m.docs or a in m.prob['params'] or (n and a.lower().startswith('prueba') and
                                                    1 <= int(n.group(1)) <= len(m.pruebas)):
            validas.append(a)
    return validas


def _propone_valor(m, texto):
    """¿Nombra un parámetro junto a un valor posible suyo? (detector mecánico de «resolver por el resolutor»)."""
    for p, vals in m.vis['valores'].items():
        if p in texto and any(re.search(rf'\b{re.escape(v.split()[0])}\b', texto) for v in vals):
            return True
    return False


def procesar(m, estado):
    """Estado del detector o de AUTO → etiquetado por código, sin descartar nada."""
    estado = estado or {}
    hechos = [{'texto': str(h.get('texto', '')), 'apoyo': _anclas_validas(m, h.get('apoyo'))}
              for h in estado.get('hechos') or [] if isinstance(h, dict)]
    hip = [{'texto': str(h.get('texto', '')), 'como': str(h.get('como_contrastar', ''))}
           for h in estado.get('hipotesis') or [] if isinstance(h, dict)]
    nec = []
    for n in estado.get('necesidades') or []:
        if not isinstance(n, dict):
            continue
        anclas = _anclas_validas(m, n.get('ancla'))
        tipo = n.get('tipo') if n.get('tipo') in ('demostrable', 'hipotetica') else 'hipotetica'
        reclasificada = tipo == 'demostrable' and not anclas
        nec.append({'texto': str(n.get('texto', '')), 'tipo': 'hipotetica' if reclasificada else tipo,
                    'reclasificada': reclasificada, 'anclas': anclas, 'como': str(n.get('como_investigar', ''))})
    textos = [x['texto'] for x in hechos + hip + nec]
    return {'hechos': hechos, 'hipotesis': hip, 'necesidades': nec,
            'proponen_valor': sum(_propone_valor(m, t) for t in textos)}


def formatear(p, origen):
    lineas = [f'Estado de necesidades ({origen}; el código solo comprueba que las referencias existen, no que digan '
              'lo que se afirma; la decisión es tuya):']
    con = [h for h in p['hechos'] if h['apoyo']]
    sin = [h for h in p['hechos'] if not h['apoyo']]
    if con:
        lineas.append('Hechos con apoyo citado: ' + ' | '.join(f'{h["texto"]} [{", ".join(h["apoyo"])}]' for h in con))
    if sin:
        lineas.append('Hechos sin apoyo verificado: ' + ' | '.join(h['texto'] for h in sin))
    if p['hipotesis']:
        lineas.append('Hipótesis: ' + ' | '.join(h['texto'] + (f' (cómo contrastar: {h["como"]})' if h['como'] else '')
                                                for h in p['hipotesis']))
    comp = [n for n in p['necesidades'] if n['tipo'] == 'demostrable']
    hipo = [n for n in p['necesidades'] if n['tipo'] == 'hipotetica']
    if comp:
        lineas.append('Necesidades comprobables: ' + ' | '.join(f'{n["texto"]} [{", ".join(n["anclas"])}]' for n in comp))
    if hipo:
        lineas.append('Necesidades hipotéticas, pendientes de contrastar: ' + ' | '.join(
            n['texto'] + (' (sin ancla válida)' if n['reclasificada'] else '') +
            (f' (cómo investigar: {n["como"]})' if n['como'] else '') for n in hipo))
    return '\n'.join(lineas)


def indice(m):
    return '\n'.join(f'{d["id"]} · día {d["dia"]} · {d["tipo"]} · {d["titulo"]}' for d in m.vis['documentos'])


def traza(m):
    """Lo que ve el detector: encargo, índice (solo metadatos), lo leído, búsquedas, pruebas y notas."""
    leidos = list(dict.fromkeys(d for _, d in m.lecturas))
    partes = [m.encargo(), 'Índice de documentos (solo metadatos):\n' + indice(m),
              'Búsquedas hechas: ' + ('; '.join(q for _, q in m.consultas) or 'ninguna'),
              'Documentos leídos por la instancia:\n' + ('\n\n'.join(m.leer(i) for i in leidos) or 'ninguno'),
              'Pruebas ejecutadas:\n' + ('\n'.join(
                  f'prueba {k + 1}: cambios {{{", ".join(f"{p}: {O.L.valor(m.prob, p, n)}" for p, n in t["cambios"].items())}}} '
                  f'→ fallan {t["fallan"]}{": " + "; ".join(t.get("fallan_nombres", [])) if t["fallan"] else ""}'
                  for k, t in enumerate(m.pruebas)) or 'ninguna'),
              'Notas: ' + m.ver_estado()]
    return '\n\n'.join(partes)


class Detector:
    """Revisión de DET: otra instancia (Haiku), con su gasto sumado al del episodio."""

    def __init__(self, cliente, modelo=MODELO_DETECTOR):
        self.cliente, self.modelo, self.registro = cliente, modelo, []

    def __call__(self, m, contexto):
        if len(self.registro) >= MAX_REVISIONES:
            return ''
        entregas = []

        def entregar_estado(**estado):
            entregas.append(estado)
            return 'Recibido.'
        h = [Herramienta('entregar_estado', 'Entrega el estado: hechos, hipótesis y necesidades.', ESQUEMA_ESTADO,
                         entregar_estado, terminal=True)]
        sub = Presupuesto(m.presupuesto.restante(), modelo=self.modelo, esfuerzo=m.presupuesto.esfuerzo)
        try:
            correr(self.cliente, SISTEMA_DETECTOR, traza(m), h, sub, 'detector', max_turnos=2)
        finally:
            m.presupuesto.gastado += sub.gastado
            m.presupuesto.llamadas += sub.llamadas
            m.presupuesto.interrupciones += sub.interrupciones
        p = procesar(m, entregas[-1] if entregas else None)
        self.registro.append({'contexto': contexto, 'origen': 'detector', 'llamada': len(m.presupuesto.llamadas),
                              'leidos_hasta': sorted({d for _, d in m.lecturas}), 'entregado': bool(entregas), **p})
        return '\n\n' + formatear(p, 'lo genera otra instancia') if entregas else ''


class Auto:
    """Revisión de AUTO: en los mismos momentos que DET y con la misma información (el índice incluido), se pide al
    propio resolutor que registre el mismo formato con registrar_estado; recibe el mismo bloque procesado."""

    def __init__(self):
        self.registro, self.pausas = [], 0

    def __call__(self, m, contexto):
        if self.pausas >= MAX_REVISIONES:
            return ''
        self.pausas += 1
        # el índice, solo en la primera pausa: después sigue en su contexto (repetirlo multiplicaba el coste sin dar
        # información nueva; el detector de DET lo recibe cada vez porque empieza cada revisión sin memoria)
        idx = f' Índice de documentos (solo metadatos):\n{indice(m)}\n' if self.pausas == 1 else ' (El índice de documentos está en la primera pausa.) '
        return (f'\n\nPausa de revisión ({self.pausas} de {MAX_REVISIONES}).{idx}{TEXTO_REVISION} '
                'Regístralo con registrar_estado antes de seguir.')

    def herramienta(self, m, contexto):
        def registrar_estado(**estado):
            p = procesar(m, estado)
            self.registro.append({'contexto': contexto, 'origen': 'propio', 'llamada': len(m.presupuesto.llamadas),
                                  'leidos_hasta': sorted({d for _, d in m.lecturas}), 'entregado': True, **p})
            return formatear(p, 'lo has registrado tú')
        return [Herramienta('registrar_estado', 'Registra el estado: hechos, hipótesis y necesidades.', ESQUEMA_ESTADO,
                            registrar_estado)]


def rama_det(cliente, prob, presupuesto):
    return O.rama_a_igual(cliente, prob, presupuesto, revision=Detector(cliente))


def rama_det_x(cliente, prob, presupuesto):
    return O.rama_x(cliente, prob, presupuesto, revision=Detector(cliente))


def rama_auto(cliente, prob, presupuesto):
    a = Auto()
    return O.rama_a_igual(cliente, prob, presupuesto, revision=a, extra=a.herramienta)


RAMAS_NEC = {'D': O.rama_a_igual, 'COB': partial(O.rama_a_igual, cobertura=True), 'DET': rama_det,
             'DET_X': rama_det_x, 'AUTO': rama_auto}
