"""Comparación A / A_PISTA / A+ / X (notas/diseno-a-aplus-x.md). Problemas sueltos, cada uno desde cero, sin almacén.

| A | actuar, leer, ejecutar_python, validar (3) y entregar |
| A_PISTA | A + un párrafo que sugiere plantear varias explicaciones y contrastarlas con los datos |
| A_MAS (A+) | A_PISTA + el módulo `contraste` en el taller (solo analiza hipótesis escritas por el modelo) |
| X | A + `abrir_contexto(encargo)`, descrita de forma neutra; los contextos comparten taller, máquina y presupuestos |

Igual para los cuatro: mismo sistema, mismo enunciado (más su párrafo), misma máquina y mismos escenarios; la
exploración queda también en `exploracion.jsonl` del taller; mismos topes de dólares, pasos, validaciones y segundos
por ejecución. Se guardan la conversación completa (también la de cada contexto de X) y el tiempo de CPU de cada
ejecución de código.
"""
import json
import random
import resource
import shutil
import time
from pathlib import Path

from ejecutor.agente import Herramienta, correr
from generadores import maquinas as G

from . import maquinas_entorno as E
from . import maquinas_ramas as R
from . import maquinas_retro as RT

BRAZOS = ('A', 'A_PISTA', 'A_MAS', 'X')
MAX_TURNOS = R.MAX_TURNOS
MAX_TURNOS_CONTEXTO = 30
MAX_RESPUESTA = 4000
CONTRASTE = Path(__file__).resolve().parent / 'taller' / 'contraste.py'

EXPLORACION = 'Lo que observas al actuar sobre la máquina (también desde código) queda en exploracion.jsonl del taller.\n'
PISTA = ('Antes de corregir un controlador que falla, puedes plantear varias explicaciones de lo que hace la máquina y '
         'contrastarlas ajustándolas a los datos que has observado.\n')
MODULO = ('En el taller tienes el módulo `contraste` (`import contraste`; su documentación, con '
          '`help(contraste)`): ajusta a los datos observados hipótesis que escribas tú como funciones de simulación y '
          'dice cuáles explican los datos y cuáles no se pueden distinguir con ellos. No propone hipótesis.\n')
SISTEMA_CONTEXTO = (R.SISTEMA.split('. Tu objetivo')[0] + '. Otra instancia que trabaja en este problema te hace un '
                    'encargo. Compartes con ella el taller, la máquina y los presupuestos. Cuando termines, contesta '
                    'con responder(texto).')
DESCRIPCION_CONTEXTO = ('Abre otra instancia del modelo, con un contexto nuevo, que trabaja en este mismo problema: '
                        'recibe tu encargo y el enunciado, comparte contigo el taller, la máquina y los presupuestos, '
                        'tiene tus herramientas salvo entregar y abrir_contexto, y te devuelve su respuesta '
                        f'(hasta {MAX_RESPUESTA} caracteres).')


def plano(x):
    """Contenido de la API (objetos) a JSON: para guardar la conversación entera."""
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    if isinstance(x, dict):
        return {k: plano(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [plano(v) for v in x]
    if hasattr(x, 'model_dump'):
        return plano(x.model_dump())
    if hasattr(x, '__dict__'):
        return plano(vars(x))
    return str(x)


def _cpu_hijos():
    r = resource.getrusage(resource.RUSAGE_CHILDREN)
    return r.ru_utime + r.ru_stime


class Mundo(E.Mundo):
    """El mundo del laboratorio B, con la exploración escrita también en el taller y el tiempo de cada ejecución."""

    def actuar(self, secuencia, reiniciar=False, origen='herramienta'):
        lecturas = super().actuar(secuencia, reiniciar, origen)
        with (self.taller / 'exploracion.jsonl').open('a') as f:
            f.write(json.dumps({'reiniciar': reiniciar, 'secuencia': self.acciones[-1]['secuencia'],
                                'lecturas': lecturas}) + '\n')
        return lecturas

    def ejecutar(self, codigo):
        t0, c0 = time.monotonic(), _cpu_hijos()
        salida = super().ejecutar(codigo)
        self.ejecuciones[-1].update(segundos=round(time.monotonic() - t0, 2), cpu=round(_cpu_hijos() - c0, 2))
        return salida


def enunciado(prob, brazo, almacen):
    texto = R.enunciado(prob, brazo, 1, 1, almacen) + EXPLORACION
    if brazo in ('A_PISTA', 'A_MAS'):
        texto += PISTA
    if brazo == 'A_MAS':
        texto += MODULO
    return texto


def herramienta_contexto(cliente, m, presupuesto, validaciones, contextos, texto_enunciado):
    def abrir_contexto(encargo):
        if not isinstance(encargo, str) or not encargo.strip():
            raise ValueError('encargo: el texto de lo que pides a la otra instancia')
        respuesta = []
        hs = [h for h in E.herramientas(m, [], codigo_libre=True, persistente=False) if h.nombre != 'entregar']
        hs += [RT.herramienta_validar(m, validaciones),
               Herramienta('responder', 'Devuelve tu respuesta a la instancia que te hizo el encargo. Termina tu trabajo.',
                           {'type': 'object', 'properties': {'texto': {'type': 'string'}}, 'required': ['texto']},
                           lambda texto: respuesta.append(str(texto)) or 'Enviado.', terminal=True)]
        n = len(contextos) + 1
        r = correr(cliente, SISTEMA_CONTEXTO, f'Encargo:\n{encargo}\n\nEnunciado del problema:\n{texto_enunciado}', hs,
                   presupuesto, f'contexto_{n}', max_turnos=MAX_TURNOS_CONTEXTO)
        texto = (respuesta[-1] if respuesta else r['texto'] or '(terminó sin responder)')[:MAX_RESPUESTA]
        contextos.append({'n': n, 'encargo': encargo, 'respuesta': texto, 'turnos': r['turnos'], 'agotado': r['agotado'],
                          'conversacion': plano(r['mensajes']), 'texto_final': r['texto']})
        return texto
    return Herramienta('abrir_contexto', DESCRIPCION_CONTEXTO,
                       {'type': 'object', 'properties': {'encargo': {'type': 'string'}}, 'required': ['encargo']},
                       abrir_contexto)


def episodio(cliente, prob, brazo, taller, presupuesto):
    """Un problema con un brazo. Devuelve la fila de resultados (evaluación en los escenarios retenidos, por código)."""
    if brazo not in BRAZOS:
        raise ValueError(f'brazo desconocido: {brazo}')
    m = Mundo(prob, taller, presupuesto, cliente)
    if brazo == 'A_MAS':
        shutil.copy2(CONTRASTE, m.taller / '.sistema' / 'contraste.py')
    entregas, validaciones, contextos = [], [], []
    texto = enunciado(prob, brazo, m.taller / 'almacen')
    hs = E.herramientas(m, entregas, codigo_libre=True, persistente=False) + [RT.herramienta_validar(m, validaciones)]
    if brazo == 'X':
        hs.append(herramienta_contexto(cliente, m, presupuesto, validaciones, contextos, texto))
    cpu0 = _cpu_hijos()
    r = correr(cliente, R.SISTEMA, texto, hs, presupuesto, brazo, max_turnos=MAX_TURNOS)
    ev = E.evaluar_controlador(m, entregas[-1]) if entregas else {'puntuacion': 0.0, 'error': 'sin entrega', 'usos': [],
                                                                         'importados': []}
    return {'brazo': brazo, 'entregado': bool(entregas), 'controlador': entregas[-1] if entregas else None, **ev,
            'pasos': m.pasos, 'acciones': m.acciones, 'ejecuciones': m.ejecuciones, 'consultas_modelo': len(m.consultas),
            'turnos': r['turnos'], 'codigo_entregado': (m.taller / entregas[-1]).read_text() if entregas else None,
            'validaciones': validaciones,
            'controladores_validados': {v['ruta']: (m.taller / v['ruta']).read_text() for v in validaciones},
            'cpu_codigo': round(sum(e.get('cpu', 0) for e in m.ejecuciones), 2),
            'cpu_total': round(_cpu_hijos() - cpu0, 2),
            'enunciado': texto, 'conversacion': plano(r['mensajes']), 'texto_final': r['texto'], 'contextos': contextos}


# --------------------------------------------------------------------------------------------------- banco

def dificultad(cal):
    """Referencia mecánica de dificultad: lo mejor de los métodos convencionales (la magnitud que define el estrato)."""
    return max(cal['ingenuo'], cal['generico'])


def banco(semilla, n, intentos=400, con_aliasing=None, tope_d=None):
    """Problemas sueltos del estrato difícil, con la distribución natural del generador (regla fijada antes de
    generar): de 1 a 4 mecanismos no lineales al azar y, con probabilidad 0,5, un lineal acompañante; se aceptan si el
    ideal los resuelve (≥ 0,9) y los métodos convencionales no (estrato «difícil»). Sin filtrar por tipo.
    Banco equilibrado (§11 del diseño): `con_aliasing` fija cuántos de los n llevan aliasing (los primeros en orden de
    cada grupo; un candidato de un grupo lleno se descarta) y `tope_d` es un tope de dificultad común a los dos grupos."""
    rng, salida = random.Random(f'banco-hipotesis-{semilla}'), []
    cupo = None if con_aliasing is None else {True: con_aliasing, False: n - con_aliasing}
    for k in range(intentos):
        if len(salida) == n:
            break
        tipos = rng.sample(G.NO_LINEALES, rng.randint(1, len(G.NO_LINEALES)))
        tipos += [rng.choice(G.LINEALES)] if rng.random() < 0.5 else []
        grupo = 'aliasing' in tipos
        if cupo is not None and sum(('aliasing' in p['tipos']) == grupo for p in salida) >= cupo[grupo]:
            continue
        ps = f'{semilla}-{k + 1}'
        cal = G.calibrar(G.construir(ps, tipos))
        if cal['ideal'] >= G.UMBRAL_IDEAL and cal['estrato'] == 'dificil' and (tope_d is None or dificultad(cal) <= tope_d):
            salida.append({'semilla': ps, 'tipos': sorted(tipos), **cal})
    if len(salida) < n:
        raise RuntimeError(f'banco {semilla}: solo {len(salida)} problemas en {intentos} intentos')
    return salida
