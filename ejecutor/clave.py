"""Credenciales de las APIs de modelos (Claude y OpenAI) desde `.env` (fuera de git), sin dependencias: lo usan los
proveedores propios y el entorno de τ-bench. Nunca se imprimen."""
import os
from pathlib import Path

ENV = Path(__file__).resolve().parent.parent / '.env'      # fuera de git (.gitignore)


VARIABLES = ('ANTHROPIC_API_KEY', 'ANTHROPIC_WORKSPACE_ID', 'OPENAI_API_KEY', 'OPENAI_API_SECRET', 'OPENAI_ORG_ID',
             'OPENAI_PROJECT_ID')


def cargar_clave(env=ENV):
    """Pone ANTHROPIC_API_KEY (y ANTHROPIC_WORKSPACE_ID, si la clave no va ligada a un espacio de trabajo) desde `.env`
    y OPENAI_API_KEY cuando el entorno no las trae. Solo esas variables; nunca se imprimen."""
    if not env.exists():
        return
    for linea in env.read_text().splitlines():
        clave, _, valor = linea.strip().removeprefix('export ').partition('=')
        clave, valor = clave.strip(), valor.strip().strip('"\'')
        if clave in VARIABLES and valor and not os.environ.get(clave):
            os.environ[clave] = valor
