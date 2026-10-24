"""Brazos y fases del laboratorio B (notas/diseno-simulador-b.md §3).

Construcción (una secuencia de problemas, cada problema con una instancia nueva; solo el almacén cruza problemas):
| FIJO | actuar, leer y entregar (escribe el controlador como texto); sin ejecutar código ni almacén |
| LIBRE | además ejecutar Python en su taller; el almacén pasa de un problema al siguiente |
| LIBRE_SIN_MEMORIA | como LIBRE, pero el almacén empieza vacío en cada problema |

Al terminar la secuencia de LIBRE:
- informe: una instancia nueva ve el almacén final y los resultados de la secuencia, y escribe en prosa lo aprendido
  para otra instancia (experiencia textual equivalente, dueño), sin código y con el mismo tamaño que el texto del
  almacén (con un tope);
- repertorio: otra instancia, solo con la descripción de la interfaz y sin ninguna máquina, prepara su almacén.

Trasplante (instancia nueva, mismo presupuesto, herramientas de LIBRE; el almacén no se acumula entre problemas de
prueba):
| T0 | almacén vacío |
| T_NOTAS | almacén vacío; el informe en el enunciado |
| T_TODO | el almacén final de LIBRE |
| T_CODIGO_TEXTO | almacén vacío; el código del almacén en el enunciado como texto |
| T_REPERTORIO | el almacén del repertorio |

Nada en los textos sugiere qué construir ni cómo organizarse (dueño 22/10): se dicen el objetivo, las primitivas, los
presupuestos y que el almacén se conserva.
"""
import json
import re
import shutil
from pathlib import Path

from ejecutor.agente import Herramienta, correr
from generadores import maquinas as G

from . import maquinas_entorno as E
from . import maquinas_retro as RT

MAX_TURNOS = 60
PERSISTENTES = ('LIBRE', 'RETRO')                                 # el almacén pasa de un problema al siguiente
CON_VALIDAR = ('RETRO', 'RETRO_SIN_ALMACEN', 'TRASPLANTE_RETRO')  # retroalimentación dentro del problema
CON_HISTORIAL = ('RETRO', 'RETRO_SIN_ALMACEN')                    # y de los problemas anteriores
MAX_INFORME = 8000

SISTEMA = ('Trabajas con máquinas desconocidas. Cada máquina tiene actuadores, que controlas, y canales de salida, que '
           'lees. Tu objetivo es entregar un controlador: código Python con una función controlar(lecturas, memoria) que '
           'en cada paso recibe las lecturas (una por canal) y un diccionario que conserva lo que guardes durante un '
           'escenario, y devuelve una acción por actuador. El controlador se evaluará en escenarios que no verás, con '
           'otros estados iniciales y perturbaciones: debe llevar y mantener cada salida dentro de la tolerancia del '
           'objetivo durante la ventana final. Tienes un presupuesto de pasos para interactuar con la máquina y un '
           'presupuesto de cómputo; cuando se agotan, el problema termina.')


def enunciado(prob, rama, n, total, almacen, extra='', historial=None):
    v = G.visible(prob)
    texto = (f'Problema {n} de {total}.\nMáquina: {v["actuadores"]} actuadores (de -{v["limite"]} a {v["limite"]}), '
             f'{v["canales"]} canales.\nObjetivo por canal: {v["objetivo"]}, tolerancia ±{v["tolerancia"]}.\n'
             f'Escenarios de evaluación: {v["pasos_escenario"]} pasos; se cumple si la salida está dentro de la '
             f'tolerancia en al menos el {int(v["cumple"] * 100)} % de los {v["ventana"]} pasos finales.\n'
             f'Presupuesto de pasos con esta máquina: {v["presupuesto_pasos"]}.\n')
    if rama != 'FIJO':
        ficheros = sorted(p for p in E.composicion(almacen.parent) if p.startswith('almacen/')) if almacen else []
        texto += ('Tienes un taller propio (una carpeta) donde puedes ejecutar Python. Su subcarpeta almacen/ '
                  + ('se conserva de un problema al siguiente.' if rama in PERSISTENTES else 'empieza así en este problema.')
                  + f'\nContenido actual de almacen/: {", ".join(f[8:] for f in ficheros) or "vacío"}.\n')
    if rama in CON_HISTORIAL:
        texto += ('Resultados de los problemas anteriores de esta secuencia (también en historial/ del taller):\n'
                  + RT.texto_historial(historial) + '\n')
    return texto + extra


def episodio(cliente, prob, rama, taller, presupuesto, n=1, total=1, almacen=None, extra='', historial=None):
    """Un problema. Devuelve la fila de resultados (la evaluación en escenarios retenidos, por código)."""
    m = E.Mundo(prob, taller, presupuesto, cliente, almacen)
    entregas, validaciones = [], []
    hs = E.herramientas(m, entregas, codigo_libre=rama != 'FIJO', persistente=rama in PERSISTENTES)
    if rama in CON_VALIDAR:
        hs.append(RT.herramienta_validar(m, validaciones))
    if rama in CON_HISTORIAL:
        RT.instalar_historial(m, historial)
    r = correr(cliente, SISTEMA, enunciado(prob, rama, n, total, m.taller / 'almacen', extra, historial), hs,
               presupuesto, rama, max_turnos=MAX_TURNOS)
    ev = E.evaluar_controlador(m, entregas[-1]) if entregas else {'puntuacion': 0.0, 'error': 'sin entrega', 'usos': [],
                                                                         'importados': []}
    return {'entregado': bool(entregas), 'controlador': entregas[-1] if entregas else None, **ev,
            'pasos': m.pasos, 'acciones': m.acciones, 'ejecuciones': m.ejecuciones, 'consultas_modelo': len(m.consultas),
            'inicial': m.inicial, 'final': E.composicion(m.taller), 'turnos': r['turnos'],
            'codigo_entregado': (m.taller / entregas[-1]).read_text() if entregas else None,
            'validaciones': validaciones}


# --------------------------------------------------------------------------------------------------- informe y repertorio

def texto_almacen(almacen, solo_codigo=False):
    partes = []
    for p in sorted(Path(almacen).rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts and (not solo_codigo or p.suffix == '.py'):
            try:
                partes.append(f'--- {p.relative_to(almacen)} ---\n{p.read_text()}')
            except UnicodeDecodeError:
                partes.append(f'--- {p.relative_to(almacen)} --- (binario, {p.stat().st_size} bytes)')
    return '\n'.join(partes)


SISTEMA_INFORME = ('Otra instancia resolverá máquinas nuevas de la misma clase, empezando sin nada. Escribe para ella, '
                   'en prosa y sin código, lo que se aprendió en esta secuencia y le sería útil. Entrega con '
                   'escribir_informe.')


def informe(cliente, almacen, resultados, presupuesto):
    """Experiencia textual equivalente: prosa sin código, con el tamaño del texto del almacén (tope MAX_INFORME)."""
    contenido = texto_almacen(almacen)
    limite = max(1000, min(MAX_INFORME, len(contenido)))
    salida = []

    def escribir_informe(texto):
        if len(texto) > limite:
            raise ValueError(f'el informe tiene {len(texto)} caracteres; el límite es {limite}')
        if re.search(r'```|^\s*(def|import|class)\s', texto, re.M):
            raise ValueError('el informe va en prosa, sin código')
        salida.append(texto)
        return 'Recibido.'
    mensaje = (f'Resultados de la secuencia (puntuación en escenarios retenidos por problema): {resultados}\n\n'
               f'Contenido final del almacén:\n{contenido or "(vacío)"}\n\nLímite del informe: {limite} caracteres.')
    h = [Herramienta('escribir_informe', 'Entrega el informe en prosa.', {'type': 'object', 'properties': {
        'texto': {'type': 'string'}}, 'required': ['texto']}, escribir_informe, terminal=True)]
    correr(cliente, SISTEMA_INFORME, mensaje, h, presupuesto, 'informe', max_turnos=4)
    return {'texto': salida[-1] if salida else '', 'limite': limite}


def repertorio(cliente, prob_ejemplo, taller, presupuesto):
    """Lo que el modelo prepara sin haber visto ninguna máquina: solo la interfaz (control de conocimiento previo)."""
    m = E.Mundo(prob_ejemplo, taller, presupuesto, cliente, pasos=0)
    hechos = []
    hs = [h for h in E.herramientas(m, [], codigo_libre=True) if h.nombre == 'ejecutar_python']
    hs.append(Herramienta('terminar', 'Termina la preparación.', {'type': 'object', 'properties': {}},
                          lambda: hechos.append(1) or 'Hecho.', terminal=True))
    v = G.visible(prob_ejemplo)
    mensaje = (f'Más adelante resolverás máquinas de esta clase: {v["actuadores"]} actuadores (de -{v["limite"]} a '
               f'{v["limite"]}), {v["canales"]} canales, objetivos y tolerancias que cambian, {v["presupuesto_pasos"]} '
               'pasos de interacción por máquina. Ahora no tienes ninguna máquina. Puedes preparar lo que quieras en '
               'almacen/ de tu taller; se conservará para entonces.')
    r = correr(cliente, SISTEMA, mensaje, hs, presupuesto, 'repertorio', max_turnos=20)
    return {'ejecuciones': m.ejecuciones, 'final': E.composicion(m.taller), 'turnos': r['turnos']}


# --------------------------------------------------------------------------------------------------- trasplante

BRAZOS_TRASPLANTE = ('T0', 'T_NOTAS', 'T_TODO', 'T_CODIGO_TEXTO', 'T_REPERTORIO')
# con retroalimentación (notas/diseno-laboratorio-b-retro.md §3): la fuente es RETRO y todos tienen validar
BRAZOS_RETRO = ('T0', 'T_TODO', 'T_HISTORIAL', 'T_CODIGO_TEXTO', 'T_SIN_CODIGO')


def material_trasplante(brazo, almacen_libre, texto_informe, almacen_repertorio, texto_historial='',
                        almacen_sin_codigo=None):
    """(almacén con el que empieza, texto extra del enunciado) para cada brazo. `almacen_libre` es el almacén final
    de la rama fuente (LIBRE o RETRO)."""
    if brazo == 'T_TODO':
        return almacen_libre, ''
    if brazo == 'T_SIN_CODIGO':                       # ablación: el almacén sin lo ejecutable (quedan las notas)
        return almacen_sin_codigo, ''
    if brazo == 'T_HISTORIAL':                        # la misma experiencia, como texto, sin capacidad ejecutable
        return None, f'\nResultados de una instancia anterior que resolvió máquinas de esta clase:\n{texto_historial or "(vacío)"}\n'
    if brazo == 'T_REPERTORIO':
        return almacen_repertorio, ''
    if brazo == 'T_NOTAS':
        return None, f'\nInforme de una instancia anterior que resolvió máquinas de esta clase:\n{texto_informe or "(vacío)"}\n'
    if brazo == 'T_CODIGO_TEXTO':
        codigo = texto_almacen(almacen_libre, solo_codigo=True) if almacen_libre else ''
        return None, f'\nCódigo que escribió una instancia anterior con máquinas de esta clase (solo como texto):\n{codigo or "(ninguno)"}\n'
    return None, ''


def sin_codigo(almacen, destino):
    """Copia del almacén sin ficheros ejecutables (.py) ni cachés."""
    return copiar_almacen(Path(almacen).parent, destino, origen=Path(almacen).name, ignorar=('__pycache__', '*.py'))


def copiar_almacen(taller, destino, origen='almacen', ignorar=('__pycache__',)):
    destino = Path(destino)
    if destino.exists():
        shutil.rmtree(destino)
    shutil.copytree(Path(taller) / origen, destino, ignore=shutil.ignore_patterns(*ignorar))
    return destino
