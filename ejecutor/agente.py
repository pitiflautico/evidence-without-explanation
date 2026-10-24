"""Bucle de agente con herramientas sobre la API de Claude, con presupuesto en dólares por episodio impuesto por código.

Lo comparten todas las ramas de A–E (notas/diseno-abcd.md): mismo modelo, mismo esfuerzo, mismas herramientas y mismo
presupuesto; lo único que cambia entre ramas es cómo se organiza el trabajo. Bucle manual según la referencia de la
API: se devuelve `response.content` completo (incluido el razonamiento), los resultados de herramientas van en un
mensaje de usuario, `tool_choice` automático (forzar una herramienta da 400 en Opus 5.5) y caché automática.

Antes de cada llamada se reserva su peor coste; si no cabe en lo que queda del episodio, el agente termina sin
respuesta (`agotado`). Cada llamada se registra con su rol (etiqueta), tokens, coste y herramientas pedidas.
"""
import json
import time
from dataclasses import dataclass, field

from ejecutor.claude import dolares

MODELO = 'claude-opus-5-5'
ESFUERZO = 'low'
MAX_TOKENS = 4000
CARACTERES_POR_TOKEN = 3.0


class PresupuestoAgotado(Exception):
    pass


@dataclass
class Presupuesto:
    """Dinero de un episodio, compartido por todos los agentes de una rama (incluidos subagentes)."""
    maximo: float
    gastado: float = 0.0
    modelo: str = MODELO                                       # cómputo del episodio (fase 2: Opus o Haiku, esfuerzo)
    esfuerzo: str | None = ESFUERZO                            # None: sin parámetro de esfuerzo
    llamadas: list = field(default_factory=list)
    interrupciones: list = field(default_factory=list)      # (rol, motivo) de cada agente que no terminó

    def restante(self):
        return self.maximo - self.gastado

    def reservar(self, caracteres, max_tokens):
        # peor caso: toda la entrada se escribe en caché (más cara que la entrada sin caché) y la salida es máxima
        peor = dolares(self.modelo, 0, 0, caracteres / CARACTERES_POR_TOKEN, max_tokens)
        if peor > self.restante():
            raise PresupuestoAgotado(f'quedan {self.restante():.3f} $ y la llamada podría costar {peor:.3f} $')


@dataclass
class Herramienta:
    nombre: str
    descripcion: str
    esquema: dict
    funcion: object                    # funcion(**entrada) -> str ; puede lanzar ValueError (vuelve como error)
    terminal: bool = False             # si se llama y no da error, el agente termina con su resultado

    def definicion(self):
        return {'name': self.nombre, 'description': self.descripcion, 'input_schema': self.esquema}


def correr(cliente, sistema, mensaje, herramientas, presupuesto, etiqueta, max_turnos=16, previos=None):
    """Ejecuta un agente hasta que llama a una herramienta terminal, deja de pedir herramientas o se agota.
    Devuelve {'terminal': (nombre, entrada) | None, 'texto': str, 'turnos': n, 'agotado': bool, 'mensajes': [...]}.
    `previos`: continuar la misma conversación (una sola instancia, p. ej. D): el mensaje nuevo se añade al último
    turno del usuario (la API exige alternancia)."""
    por_nombre = {h.nombre: h for h in herramientas}
    definiciones = [h.definicion() for h in herramientas]
    if previos:
        mensajes = [dict(m) for m in previos]
        ultimo = mensajes[-1]
        contenido = ultimo['content'] if isinstance(ultimo['content'], list) else [{'type': 'text', 'text': ultimo['content']}]
        mensajes[-1] = {'role': 'user', 'content': [*contenido, {'type': 'text', 'text': mensaje}]}
    else:
        mensajes = [{'role': 'user', 'content': mensaje}]
    texto, turnos = '', 0
    while turnos < max_turnos:
        turnos += 1
        caracteres = len(sistema) + len(json.dumps(definiciones)) + len(json.dumps(mensajes, default=str))
        try:
            presupuesto.reservar(caracteres, MAX_TOKENS)
        except PresupuestoAgotado:
            presupuesto.interrupciones.append((etiqueta, 'presupuesto agotado'))
            return {'terminal': None, 'texto': texto, 'turnos': turnos, 'agotado': True, 'mensajes': mensajes}
        t0 = time.monotonic()
        extra = {'output_config': {'effort': presupuesto.esfuerzo}} if presupuesto.esfuerzo else {}
        r = cliente.messages.create(model=presupuesto.modelo, max_tokens=MAX_TOKENS, system=sistema, tools=definiciones,
                                    messages=mensajes, cache_control={'type': 'ephemeral'}, **extra)
        u = r.usage
        leida, escrita = getattr(u, 'cache_read_input_tokens', 0) or 0, getattr(u, 'cache_creation_input_tokens', 0) or 0
        coste = dolares(presupuesto.modelo, u.input_tokens, leida, escrita, u.output_tokens)
        presupuesto.gastado += coste
        pedidas = [b for b in r.content if b.type == 'tool_use']
        presupuesto.llamadas.append({'rol': etiqueta, 'modelo': presupuesto.modelo, 'tokens_in': u.input_tokens + leida + escrita, 'cache_leida': leida,
                                     'tokens_out': u.output_tokens, 'dolares': round(coste, 5),
                                     'segundos': round(time.monotonic() - t0, 2), 'herramientas': [b.name for b in pedidas],
                                     # instrumentación (19/10, sin efecto en prompts): qué pidió, para analizar lecturas
                                     # las entregas se guardan completas (cada intento, también los rechazados)
                                     'argumentos': [json.dumps(b.input, ensure_ascii=False, default=str)[:None if b.name == 'proponer_reparto' else 300]
                                                    for b in pedidas],
                                     'stop_reason': r.stop_reason})
        texto = ''.join(b.text for b in r.content if b.type == 'text') or texto
        if r.stop_reason == 'refusal' or not pedidas:
            presupuesto.interrupciones.append((etiqueta, 'rechazo' if r.stop_reason == 'refusal' else 'terminó sin entregar'))
            return {'terminal': None, 'texto': texto, 'turnos': turnos, 'agotado': False, 'mensajes': mensajes}
        mensajes.append({'role': 'assistant', 'content': r.content})
        resultados, terminal = [], None
        for b in pedidas:
            h = por_nombre.get(b.name)
            try:
                if h is None:
                    raise ValueError(f'la herramienta «{b.name}» no existe')
                salida, error = h.funcion(**(b.input or {})), False
                if h.terminal and terminal is None:
                    terminal = (b.name, b.input)
            except (ValueError, TypeError) as e:
                salida, error = f'Error: {e}', True
            resultados.append({'type': 'tool_result', 'tool_use_id': b.id, 'content': str(salida), 'is_error': error})
            if error:                         # instrumentación (19/10): errores devueltos, para medir reparaciones
                presupuesto.llamadas[-1].setdefault('errores', []).append(f'{b.name}: {str(salida)[:200]}')
        mensajes.append({'role': 'user', 'content': resultados})
        if terminal:
            return {'terminal': terminal, 'texto': texto, 'turnos': turnos, 'agotado': False, 'mensajes': mensajes}
    presupuesto.interrupciones.append((etiqueta, f'sin entregar tras {max_turnos} turnos'))
    return {'terminal': None, 'texto': texto, 'turnos': turnos, 'agotado': False, 'mensajes': mensajes}
