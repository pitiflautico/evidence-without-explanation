import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class Uso:
    def __init__(self, entrada=100, cache=40, salida=10):
        self.input_tokens, self.cached_input_tokens, self.output_tokens = entrada, cache, salida


class Respuesta:
    def __init__(self, texto):
        self.text, self.usage = texto, Uso()


class Simulado:
    """Proveedor simulado: responde JSON válido según el tipo de prompt. `fijas` fuerza la respuesta por marcador."""

    def __init__(self, t1='elevar', t3='elevar_al_dueño'):
        self.t1, self.t3, self.prompts, self.kw = t1, t3, [], []

    def complete(self, prompt, **kw):
        self.prompts.append(prompt)
        self.kw.append(kw)
        if 'ENCARGOS NUMERADOS' in prompt:
            n = prompt.split('ENCARGOS NUMERADOS:\n', 1)[1].count('\n') + 1
            return Respuesta(json.dumps({'respuestas': [{'n': i, 'respuesta': self.t1} for i in range(1, n + 1)]}))
        if 'PROPUESTAS NUMERADAS' in prompt:
            n = prompt.split('PROPUESTAS NUMERADAS:\n', 1)[1].count('\n') + 1
            return Respuesta(json.dumps({'respuestas': [{'n': i, 'respuesta': self.t3, 'decision': None}
                                                        for i in range(1, n + 1)]}))
        if 'Fallaste el último encargo' in prompt:
            correcta = prompt.split('Lo correcto era «', 1)[1].split('»', 1)[0]
            return Respuesta(json.dumps({'texto': 'lección general de prueba', 'respuesta': correcta,
                                         'por_que': 'corrección', 'cubre': []}))
        if 'Clasifica este episodio' in prompt:
            episodio = prompt.split('[EPISODIO]\n', 1)[1]
            ids = re.findall(r'\bD-\d+\b', episodio)
            es_dec, did = bool(ids), (ids[0] if ids else None)
            return Respuesta(json.dumps({'tipo': 'decision' if es_dec else 'otro', 'del_negocio_propio': es_dec,
                                         'id': did, 'tema': 'tema', 'resumen': 'r'}))
        if '¿Se puede hacer hoy?' in prompt:
            return Respuesta(json.dumps({'respuesta': self.t3, 'decision': None}))
        return Respuesta(json.dumps({'respuesta': self.t1, 'accion': 'encargo', 'lecciones_usadas': []}))
