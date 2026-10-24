"""Retroalimentación de resultados del laboratorio B (notas/diseno-laboratorio-b-retro.md §1). Solo cambia el acceso a
las consecuencias: ni el generador, ni los problemas, ni la evaluación final.

- Escenarios de validación: 6 por problema, con las mismas reglas que los de evaluación pero de otro espacio de
  semillas (`val-<semilla>-<k>`); los 12 de evaluación siguen sin verse.
- `validar`: corre el controlador en el taller aislado sobre esos escenarios (como mucho VALIDACIONES veces por
  problema, sin gastar pasos de exploración). Devuelve, por escenario, si cumple, la fracción de la ventana final en
  tolerancia y un resumen de la trayectoria. La trayectoria completa (lecturas y acciones) queda en
  `validaciones/<n>.json` del taller. Es una señal general: lo que verían los sensores y el resultado; nunca la
  especificación, la salida verdadera, el régimen, el estado inicial ni la perturbación.
- Historial entre problemas: puntuación final (escenarios de evaluación) y resúmenes de validación de cada problema
  anterior, sin código, en `historial/` del taller.
"""
import json
import random
import shutil
from pathlib import Path

from ejecutor.agente import Herramienta
from generadores import maquinas as G

VALIDACIONES = 3
N_VALIDACION = 6
CADA = 10


def escenarios_validacion(prob):
    return [G.inicial_aleatorio(random.Random(f'val-{prob["semilla"]}-{k}'), prob['espec'], escenario=True)
            for k in range(N_VALIDACION)]


def escenario_validacion(prob, k, ini, controlar):
    """(pasos con lecturas y acciones, fracción de la ventana final en tolerancia) de un escenario de validación."""
    maq = G.Maquina(prob['espec'], ini, f'ruido-val-{prob["semilla"]}-{k}')
    memoria, lec, dentro, pasos = {}, maq.lecturas(), 0, []
    for t in range(G.PASOS_ESCENARIO):
        u = [round(float(a), 3) for a in controlar(lec, memoria)]
        lec = maq.paso(u)
        pasos.append({'t': t, 'acciones': u, 'lecturas': lec})
        if t >= G.PASOS_ESCENARIO - G.VENTANA:
            dentro += all(abs(y - o) <= prob['tol'] for y, o in zip(maq.salida(), prob['objetivo']))
    return pasos, dentro / G.VENTANA


def validar(m, ruta, n):
    """Resultados de la validación n del controlador `ruta` del taller de `m`; escribe la trayectoria completa."""
    c = m.controlador(ruta)
    escenarios, trayectorias = [], []
    try:
        for k, ini in enumerate(escenarios_validacion(m.prob)):
            pasos, fraccion = escenario_validacion(m.prob, k, ini, c)
            escenarios.append({'escenario': k + 1, 'cumplido': fraccion >= G.CUMPLE, 'fraccion_ventana': round(fraccion, 3),
                               'resumen': [p for p in pasos if p['t'] % CADA == 0 or p['t'] == G.PASOS_ESCENARIO - 1]})
            trayectorias.append({'escenario': k + 1, 'pasos': pasos})
    finally:
        c.cerrar()
    if c.error:
        raise ValueError(f'el controlador no funciona: {c.error}')
    (m.taller / 'validaciones').mkdir(exist_ok=True)
    (m.taller / 'validaciones' / f'{n}.json').write_text(json.dumps(trayectorias))
    return {'validacion': n, 'cumplidos': sum(e['cumplido'] for e in escenarios), 'de': len(escenarios),
            'escenarios': escenarios}


def herramienta_validar(m, registro):
    """`registro` acumula los resultados (para la medición). Acepta código o ruta, como entregar."""
    def funcion(codigo=None, ruta=None):
        if len(registro) >= VALIDACIONES:
            raise ValueError(f'no quedan validaciones (usadas {len(registro)} de {VALIDACIONES})')
        if codigo:
            ruta = f'validaciones/controlador_{len(registro) + 1}.py'
            (m.taller / 'validaciones').mkdir(exist_ok=True)
            (m.taller / ruta).write_text(codigo)
        if not ruta or not (m.taller / ruta).resolve().is_relative_to(m.taller) or not (m.taller / ruta).is_file():
            raise ValueError('valida `codigo` o la `ruta` de un fichero del taller que defina controlar(lecturas, memoria)')
        r = validar(m, ruta, len(registro) + 1)
        registro.append({'ruta': ruta, 'cumplidos': r['cumplidos'], 'paso_maquina': m.pasos,
                         'fracciones': [e['fraccion_ventana'] for e in r['escenarios']]})
        r['quedan'] = VALIDACIONES - len(registro)
        return json.dumps(r)
    return Herramienta(
        'validar', f'Prueba un controlador (código o ruta en el taller) en {N_VALIDACION} escenarios de validación, '
        'distintos de los de la evaluación final, con otros estados iniciales y perturbaciones. Devuelve, por escenario, '
        'si cumple, la fracción de la ventana final dentro de la tolerancia y las lecturas y acciones cada '
        f'{CADA} pasos; la trayectoria completa queda en validaciones/<n>.json del taller. No gasta pasos de la máquina. '
        f'Como mucho {VALIDACIONES} veces por problema.',
        {'type': 'object', 'properties': {'codigo': {'type': 'string'}, 'ruta': {'type': 'string'}}}, funcion)


# --------------------------------------------------------------------------------------------------- historial

def anotar_historial(carpeta, n, fila):
    """Añade al historial de una rama lo que se supo del problema n: sin código."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / f'problema_{n}.json').write_text(json.dumps({
        'problema': n, 'puntuacion_final': fila['puntuacion'], 'entregado': fila['entregado'], 'pasos': fila['pasos'],
        'turnos': fila['turnos'],
        'validaciones': [v['fracciones'] for v in fila.get('validaciones', [])]}, ensure_ascii=False))


def instalar_historial(m, carpeta):
    """Copia el historial en el taller (antes de empezar) y actualiza la composición inicial."""
    from . import maquinas_entorno as E
    if carpeta and Path(carpeta).exists():
        shutil.copytree(carpeta, m.taller / 'historial')
    else:
        (m.taller / 'historial').mkdir()
    m.inicial = E.composicion(m.taller)


def texto_historial(carpeta):
    if not carpeta or not Path(carpeta).exists():
        return '(vacío)'
    filas = [json.loads(p.read_text()) for p in sorted(Path(carpeta).glob('problema_*.json'),
                                                       key=lambda p: int(p.stem.split('_')[1]))]
    return '\n'.join(f'Problema {f["problema"]}: puntuación final {f["puntuacion_final"]:.2f}; validaciones '
                     f'(fracción de la ventana en tolerancia por escenario): {f["validaciones"] or "ninguna"}; '
                     f'pasos {f["pasos"]}' for f in filas) or '(vacío)'
