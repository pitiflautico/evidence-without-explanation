"""Proveedor Claude (API de Anthropic) con la interfaz del de Codex: `complete(prompt, effort, model) -> .text, .usage`.

Autorizado por el dueño el 19/10 para el piloto (presupuesto de 200 $), porque las llamadas por Codex se colgaban. Lo que
se mide es el sistema (la base), no el modelo; el modelo es fijo dentro de una corrida.
- Modelo: Claude Opus 5.5, el par frontera de Sol. El modelo que declara el punto (Sol) se traduce con MODELOS.
- Esfuerzo: Opus 5.5 no permite apagar el razonamiento; `none` se traduce a `low` (ESFUERZOS) y queda registrado.
- Sin `fallbacks` a otro modelo: cambiaría de modelo a escondidas a mitad del experimento. Un rechazo es un resultado.
- Uso normalizado como el de Codex: `input_tokens` es toda la entrada (sin caché + leída + escrita en caché).
"""
import os
from dataclasses import dataclass

import anthropic

from .clave import cargar_clave  # noqa: F401  (se reexporta)

MODELOS = {'gpt-5.6-sol': 'claude-opus-5-5'}     # por si un punto aún declara Sol
ESFUERZOS = {'none': 'low', 'low': 'low', 'medium': 'medium', 'high': 'high'}   # Opus/Haiku 5.5 no bajan de low
MAX_TOKENS = 16000
# $ por millón de tokens (referencia de la API, 06/10/2026): entrada, lectura de caché, escritura de caché, salida
# Haiku 5.5: caché supuesta al 10 % (lectura) y 125 % (escritura) de la entrada, como en el resto de modelos
PRECIOS = {'claude-opus-5-5': (4.00, 0.20, 5.00, 20.00), 'claude-haiku-5-5': (0.10, 0.01, 0.125, 0.50),
           # OpenAI (23/10, trackers que citan la página oficial; sin confirmar en ella): sin coste de escritura en caché
           # (se pone el precio de entrada, para que el peor caso del presupuesto no lo subestime); caché al 10 %
           'gpt-6-sol': (2.00, 0.20, 2.00, 10.00), 'gpt-6-luna': (0.10, 0.01, 0.10, 0.50)}


@dataclass
class Uso:
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    cache_write_tokens: int = 0
    dolares: float = 0.0


@dataclass
class Respuesta:
    text: str
    usage: Uso
    modelo: str
    esfuerzo: str
    stop_reason: str


def dolares(modelo, sin_cache, leida, escrita, salida):
    p_in, p_leida, p_escrita, p_out = PRECIOS[modelo]
    return (sin_cache * p_in + leida * p_leida + escrita * p_escrita + salida * p_out) / 1e6


class ClaudeProvider:
    def __init__(self, cliente=None):
        if cliente is None:
            cargar_clave()
            espacio = os.environ.get('ANTHROPIC_WORKSPACE_ID')
            cliente = anthropic.Anthropic(max_retries=4,
                                          default_headers={'anthropic-workspace-id': espacio} if espacio else None)
        self.cliente = cliente

    def complete(self, prompt, *, effort='low', model=None, **_):
        modelo = MODELOS.get(model, model) or 'claude-opus-5-5'
        esfuerzo = ESFUERZOS[effort]
        r = self.cliente.messages.create(model=modelo, max_tokens=MAX_TOKENS, output_config={'effort': esfuerzo},
                                         messages=[{'role': 'user', 'content': prompt}])
        texto = ''.join(b.text for b in r.content if b.type == 'text')
        u = r.usage
        leida, escrita = u.cache_read_input_tokens or 0, u.cache_creation_input_tokens or 0
        uso = Uso(input_tokens=u.input_tokens + leida + escrita, cached_input_tokens=leida,
                  output_tokens=u.output_tokens, cache_write_tokens=escrita,
                  dolares=dolares(modelo, u.input_tokens, leida, escrita, u.output_tokens))
        return Respuesta(text=texto, usage=uso, modelo=modelo, esfuerzo=esfuerzo, stop_reason=r.stop_reason)
