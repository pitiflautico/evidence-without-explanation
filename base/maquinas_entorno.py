"""Entorno del laboratorio B (notas/diseno-simulador-b.md §2): un taller aislado con composición conocida.

El resolutor trabaja en una carpeta propia (el taller). Al empezar, el taller solo contiene:
    almacen/             lo que se conserva entre problemas (vacío, heredado o trasplantado)
    .sistema/            el ejecutor y dos módulos cliente: maquina.py y modelo.py
Cada ejecución de código corre con sandbox-exec de macOS (sin Docker, dueño 22/10):
- sin red;
- solo puede escribir en el taller;
- no puede leer el repositorio, la carpeta personal ni /private/tmp, salvo el taller, el entorno de Python y la
  biblioteca estándar;
- entorno vacío (sin claves).
La máquina, la verdad oculta y los escenarios retenidos viven en este proceso y nunca entran en el taller. El código
habla con ellos por dos descriptores de fichero heredados (un puente JSON por líneas), sin sockets. Desde el código
puede actuar sobre la máquina y llamar al modelo, con cargo a los mismos presupuestos.

Se registra qué ficheros del almacén abre cada ejecución, incluidas las importaciones, para medir el uso de lo
construido o heredado (dueño 22/10). La composición del taller (ruta y huella) queda registrada al empezar y al
terminar.
"""
import hashlib
import json
import os
import resource
import select
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from ejecutor.agente import CARACTERES_POR_TOKEN, Herramienta, PresupuestoAgotado
from ejecutor.claude import dolares
from generadores import maquinas as G

REPO = Path(__file__).resolve().parent.parent
PYTHON = REPO / '.venv' / 'bin' / 'python'
BASE_PYTHON = Path(sys.base_prefix).resolve()
SEGUNDOS_EJECUCION = 60
SEGUNDOS_EVALUACION = 180
MAX_SALIDA = 4000
MAX_TOKENS_MODELO = 2000

PERFIL = """(version 1)
(allow default)
(deny network*)
(deny file-write* (subpath "/"))
(allow file-write* (subpath "{taller}") (literal "/dev/null"))
(deny file-read-data (subpath "/Volumes") (subpath "/Users") (subpath "/private/tmp") (subpath "/private/var/folders"))
(allow file-read-data (subpath "{taller}") (subpath "{venv}") (subpath "{base}"))
"""

EJECUTOR = r'''
import json, os, runpy, sys, types
fd_in, fd_out, modo = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
entrada, salida = os.fdopen(fd_in, 'r'), os.fdopen(fd_out, 'w')
ALMACEN = os.path.realpath('almacen')
usos, escritos, importados = set(), set(), set()   # importados: ficheros del almacén ejecutados como código


def _del_almacen(ruta):
    ruta = os.path.realpath(os.fsdecode(ruta))
    return os.path.relpath(ruta, ALMACEN) if ruta.startswith(ALMACEN + os.sep) and '__pycache__' not in ruta else None


def auditar(evento, args):
    if evento == 'compile' and len(args) > 1 and isinstance(args[1], (str, bytes)) and _del_almacen(args[1]):
        importados.add(_del_almacen(args[1]))
    if evento == 'open' and args and isinstance(args[0], (str, bytes, os.PathLike)):
        ruta = os.path.realpath(os.fsdecode(args[0]))
        if ruta.startswith(ALMACEN + os.sep) and '__pycache__' not in ruta:
            modo_ = args[1] if len(args) > 1 and isinstance(args[1], str) else 'r'
            (escritos if set(modo_) & set('wax+') else usos).add(os.path.relpath(ruta, ALMACEN))


def pedir(**peticion):
    salida.write(json.dumps(peticion) + '\n')
    salida.flush()
    r = json.loads(entrada.readline())
    if 'error' in r:
        raise RuntimeError(r['error'])
    return r['resultado']


puente = types.ModuleType('_puente')
puente.pedir = pedir
sys.modules['_puente'] = puente
sys.path[:0] = [os.path.realpath('.sistema'), ALMACEN, os.path.realpath('.')]
sys.addaudithook(auditar)
try:
    if modo == 'codigo':
        exec(compile(sys.stdin.read(), '<ejecucion>', 'exec'), {'__name__': '__main__'})
    else:
        controlar = runpy.run_path(sys.argv[4])['controlar']
        memoria = {}
        for linea in entrada:
            r = json.loads(linea)
            if r.get('fin'):
                break
            if r.get('nuevo'):
                memoria = {}
            acciones = [float(a) for a in controlar(list(r['lecturas']), memoria)]
            salida.write(json.dumps({'acciones': acciones}) + '\n')
            salida.flush()
finally:
    for m in list(sys.modules.values()):
        if isinstance(getattr(m, '__file__', None), str) and _del_almacen(m.__file__):
            importados.add(_del_almacen(m.__file__))
    salida.write(json.dumps({'op': 'fin', 'usos': sorted(usos), 'escritos': sorted(escritos),
                             'importados': sorted(importados)}) + '\n')
    salida.flush()
'''

MAQUINA_PY = '''"""Acceso a la máquina desde el código (con cargo al presupuesto de pasos)."""
from _puente import pedir


def actuar(secuencia, reiniciar=False):
    """Aplica una lista de acciones (cada una, una lista con un valor por actuador) y devuelve las lecturas tras cada paso."""
    return pedir(op='actuar', secuencia=secuencia, reiniciar=reiniciar)


def leer():
    """Lecturas actuales y pasos restantes (gratis)."""
    return pedir(op='leer')
'''

MODELO_PY = '''"""Llamar al modelo desde el código (con cargo al presupuesto del problema)."""
from _puente import pedir


def preguntar(texto, max_tokens=1000):
    return pedir(op='modelo', texto=texto, max_tokens=max_tokens)
'''


def huella(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def composicion(taller):
    """Composición del taller: ruta relativa → huella (sin .sistema, que es fijo)."""
    taller = Path(taller)
    return {str(p.relative_to(taller)): huella(p) for p in sorted(taller.rglob('*'))
            if p.is_file() and not {'.sistema', '__pycache__'} & set(p.relative_to(taller).parts)}


def preparar_taller(taller, almacen=None):
    """Crea el taller con su composición conocida: almacén (copiado de `almacen` o vacío) y .sistema."""
    taller = Path(taller).resolve()
    if taller.exists():
        shutil.rmtree(taller)
    (taller / '.sistema').mkdir(parents=True)
    if almacen:
        shutil.copytree(almacen, taller / 'almacen')
    else:
        (taller / 'almacen').mkdir()
    for nombre, texto in (('ejecutar.py', EJECUTOR), ('maquina.py', MAQUINA_PY), ('modelo.py', MODELO_PY)):
        (taller / '.sistema' / nombre).write_text(texto)
    (taller / '.sistema' / 'perfil.sb').write_text(PERFIL.format(taller=taller, venv=(REPO / '.venv').resolve(),
                                                                 base=BASE_PYTHON))
    return taller


def _limites():
    resource.setrlimit(resource.RLIMIT_CPU, (SEGUNDOS_EVALUACION, SEGUNDOS_EVALUACION))
    resource.setrlimit(resource.RLIMIT_FSIZE, (50_000_000, 50_000_000))


class Mundo:
    """Un problema en curso: la máquina viva (verdad oculta aquí), el taller, los presupuestos y los registros."""

    def __init__(self, prob, taller, presupuesto, cliente=None, almacen=None, pasos=G.PRESUPUESTO_PASOS):
        self.prob, self.presupuesto, self.cliente = prob, presupuesto, cliente
        self.taller = preparar_taller(taller, almacen)
        self.inicial = composicion(self.taller)
        self.maquina = G.maquina_exploracion(prob)
        self.pasos, self.max_pasos = 0, pasos
        self.ejecuciones, self.acciones, self.consultas = [], [], []

    # ------------------------------------------------------------------ puente
    def restantes(self):
        return self.max_pasos - self.pasos

    def actuar(self, secuencia, reiniciar=False, origen='herramienta'):
        if not isinstance(secuencia, list) or not all(isinstance(u, (list, tuple)) and len(u) == G.N_ACT for u in secuencia):
            raise ValueError(f'secuencia: lista de acciones, cada una con {G.N_ACT} valores')
        coste = len(secuencia) + (1 if reiniciar else 0)
        if coste > self.restantes():
            raise ValueError(f'quedan {self.restantes()} pasos y la petición usa {coste}')
        if reiniciar:
            self.maquina = G.maquina_exploracion(self.prob)
        self.pasos += coste
        lecturas = [self.maquina.paso(u) for u in secuencia]
        # registro completo de la exploración (dueño 23/10): sin él no se puede auditar cómo investiga el modelo
        self.acciones.append({'origen': origen, 'pasos': coste, 'reiniciar': reiniciar,
                              'secuencia': [list(map(float, u)) for u in secuencia], 'lecturas': lecturas})
        return lecturas

    def leer(self):
        return {'lecturas': self.maquina.lecturas(), 'pasos_restantes': self.restantes()}

    def preguntar_modelo(self, texto, max_tokens):
        max_tokens = min(int(max_tokens), MAX_TOKENS_MODELO)
        modelo = self.presupuesto.modelo
        peor = dolares(modelo, 0, 0, len(texto) / CARACTERES_POR_TOKEN, max_tokens)
        if self.cliente is None or peor > self.presupuesto.restante():
            raise ValueError('no queda presupuesto para llamar al modelo')
        t0 = time.monotonic()
        r = self.cliente.messages.create(model=modelo, max_tokens=max_tokens,
                                         messages=[{'role': 'user', 'content': str(texto)}])
        u = r.usage
        coste = dolares(modelo, u.input_tokens, 0, 0, u.output_tokens)
        self.presupuesto.gastado += coste
        self.presupuesto.llamadas.append({'rol': 'desde_codigo', 'modelo': modelo, 'tokens_in': u.input_tokens,
                                          'cache_leida': 0, 'tokens_out': u.output_tokens, 'dolares': round(coste, 5),
                                          'segundos': round(time.monotonic() - t0, 2), 'herramientas': [],
                                          'argumentos': [str(texto)[:300]], 'stop_reason': r.stop_reason})
        self.consultas.append(len(texto))
        return ''.join(b.text for b in r.content if getattr(b, 'type', '') == 'text')

    def atender(self, p):
        try:
            if p.get('op') == 'actuar':
                return {'resultado': self.actuar(p.get('secuencia'), bool(p.get('reiniciar')), origen='codigo')}
            if p.get('op') == 'leer':
                return {'resultado': self.leer()}
            if p.get('op') == 'modelo':
                return {'resultado': self.preguntar_modelo(p.get('texto', ''), p.get('max_tokens', 1000))}
            return {'error': f'operación desconocida: {p.get("op")}'}
        except (ValueError, TypeError, PresupuestoAgotado) as e:
            return {'error': str(e)}

    # ------------------------------------------------------------------ ejecución aislada
    def _proceso(self, modo, extra=()):
        a_hijo, de_padre = os.pipe()       # padre escribe → hijo lee
        de_hijo, a_padre = os.pipe()       # hijo escribe → padre lee
        orden = ['sandbox-exec', '-f', str(self.taller / '.sistema' / 'perfil.sb'), str(PYTHON), '-I', '-B',
                 '.sistema/ejecutar.py', str(a_hijo), str(a_padre), modo, *extra]
        proc = subprocess.Popen(orden, cwd=self.taller, env={'PATH': '/usr/bin:/bin', 'HOME': str(self.taller)},
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE if modo == 'codigo' else subprocess.DEVNULL,
                                stderr=subprocess.PIPE,
                                pass_fds=(a_hijo, a_padre), preexec_fn=_limites, text=True)
        os.close(a_hijo), os.close(a_padre)
        return proc, os.fdopen(de_padre, 'w'), os.fdopen(de_hijo, 'r')

    def ejecutar(self, codigo):
        """Ejecuta código en el taller aislado; el código puede usar `maquina` y `modelo`."""
        proc, escribir, leer = self._proceso('codigo')
        pasos_antes, usos, escritos, importados = self.pasos, [], [], []

        def servir():
            for linea in leer:
                p = json.loads(linea)
                if p.get('op') == 'fin':
                    usos.extend(p.get('usos', []))
                    escritos.extend(p.get('escritos', []))
                    importados.extend(p.get('importados', []))
                    continue
                escribir.write(json.dumps(self.atender(p)) + '\n')
                escribir.flush()
        hilo = threading.Thread(target=servir, daemon=True)
        hilo.start()
        try:
            out, err = proc.communicate(codigo, timeout=SEGUNDOS_EJECUCION)
            agotado = False
        except subprocess.TimeoutExpired:
            proc.kill()
            out, err = proc.communicate()
            agotado = True
        hilo.join(timeout=5)
        escribir.close()
        texto = (out + ('\n[stderr]\n' + err if err else ''))[-MAX_SALIDA:]
        if agotado:
            texto += f'\n[interrumpido: más de {SEGUNDOS_EJECUCION} s]'
        self.ejecuciones.append({'codigo': codigo, 'salida': texto[-1000:], 'pasos': self.pasos - pasos_antes,
                                 'usos': sorted(set(usos)), 'escritos': sorted(set(escritos)),
                                 'importados': sorted(set(importados)),
                                 'codigo_salida': proc.returncode, 'paso_maquina': self.pasos})
        return f'{texto}\n[pasos usados: {self.pasos - pasos_antes}; restantes: {self.restantes()}]'

    def controlador(self, ruta):
        """Un controlador que vive en el taller aislado: el evaluador le pasa lecturas y recibe acciones."""
        return ControladorAislado(self, ruta)


class ControladorAislado:
    def __init__(self, mundo, ruta):
        self.proc, self.escribir, self.leer = mundo._proceso('controlador', (ruta,))
        self.memoria_id, self.usos, self.importados, self.error = None, [], [], None

    def __call__(self, lecturas, memoria):
        if self.error:
            return [0.0] * G.N_ACT
        nuevo = id(memoria) != self.memoria_id
        self.memoria_id = id(memoria)
        try:
            self.escribir.write(json.dumps({'lecturas': lecturas, 'nuevo': nuevo}) + '\n')
            self.escribir.flush()
            while True:
                listo, _, _ = select.select([self.leer], [], [], 10)
                if not listo:
                    raise TimeoutError('el controlador no responde en 10 s')
                r = json.loads(self.leer.readline())
                if r.get('op') == 'fin':
                    self.usos, self.importados = r.get('usos', []), r.get('importados', [])
                    raise RuntimeError('el controlador terminó: ' + (self.proc.stderr.read() or '')[-500:])
                acciones = r['acciones']
                if len(acciones) != G.N_ACT:
                    raise ValueError(f'el controlador devolvió {len(acciones)} acciones')
                return acciones
        except (OSError, ValueError, TimeoutError, RuntimeError, json.JSONDecodeError) as e:
            self.error = str(e)[:500]
            return [0.0] * G.N_ACT

    def cerrar(self):
        try:
            self.escribir.write(json.dumps({'fin': True}) + '\n')
            self.escribir.flush()
            for linea in self.leer:
                r = json.loads(linea)
                if r.get('op') == 'fin':
                    self.usos, self.importados = r.get('usos', []), r.get('importados', [])
        except (OSError, ValueError):
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def evaluar_controlador(mundo, ruta):
    """Puntuación en escenarios retenidos de un controlador del taller (los escenarios nunca entran en el taller)."""
    c = mundo.controlador(ruta)
    try:
        puntos = G.evaluar(mundo.prob, c)
    finally:
        c.cerrar()
    return {'puntuacion': 0.0 if c.error else puntos, 'error': c.error, 'usos': c.usos, 'importados': c.importados}


def probar_controlador(mundo, ruta):
    """Comprobación previa a entregar, sin datos ocultos: que cargue y devuelva acciones para lecturas neutras."""
    c = mundo.controlador(ruta)
    try:
        c([0.0] * G.N_CAN, {})
    finally:
        c.cerrar()
    if c.error:
        raise ValueError(f'el controlador no funciona: {c.error}')


# --------------------------------------------------------------------------------------------------- herramientas

def herramientas(m, entregas, codigo_libre=True, persistente=True):
    """FIJO: actuar, leer y entregar (escribe el controlador como texto). LIBRE: además ejecutar_python y entregar
    por ruta del taller. `persistente`: si el almacén pasa al problema siguiente (la descripción no debe decirlo cuando
    no es así: ramas sin almacén y trasplante)."""
    def actuar(secuencia, reiniciar=False):
        return json.dumps({'lecturas': m.actuar(secuencia, reiniciar), 'pasos_restantes': m.restantes()})

    def leer():
        return json.dumps(m.leer())

    def entregar(codigo=None, ruta=None):
        if codigo:
            ruta = f'entregas/controlador_{len(entregas) + 1}.py'
            (m.taller / 'entregas').mkdir(exist_ok=True)
            (m.taller / ruta).write_text(codigo)
        if not ruta or not (m.taller / ruta).resolve().is_relative_to(m.taller) or not (m.taller / ruta).is_file():
            raise ValueError('entrega `codigo` o la `ruta` de un fichero del taller que defina controlar(lecturas, memoria)')
        probar_controlador(m, ruta)
        entregas.append(ruta)
        return 'Entregado.'
    h = [Herramienta('actuar', 'Aplica una secuencia de acciones a la máquina (cada acción: un valor por actuador, '
                     f'de -{G.LIMITE} a {G.LIMITE}) y devuelve las lecturas tras cada paso. Cada acción gasta un paso; '
                     'reiniciar vuelve al estado inicial y gasta uno.',
                     {'type': 'object', 'properties': {'secuencia': {'type': 'array', 'items': {'type': 'array', 'items': {'type': 'number'}}},
                                                       'reiniciar': {'type': 'boolean'}}, 'required': ['secuencia']}, actuar),
         Herramienta('leer', 'Lecturas actuales y pasos restantes (gratis).', {'type': 'object', 'properties': {}}, leer),
         Herramienta('entregar', 'Entrega el controlador: código Python que define controlar(lecturas, memoria) -> '
                     'lista de acciones' + (', o la ruta de ese fichero en el taller' if codigo_libre else '') +
                     '. Termina el problema.',
                     {'type': 'object', 'properties': {'codigo': {'type': 'string'}, **({'ruta': {'type': 'string'}} if codigo_libre else {})}},
                     entregar, terminal=True)]
    if codigo_libre:
        h.append(Herramienta('ejecutar_python', 'Ejecuta Python en tu taller (carpeta propia; sin red). Puedes leer y '
                             'escribir ficheros' + ('; `almacen/` se conserva entre problemas' if persistente else '') + '. Desde el código: '
                             '`import maquina` (maquina.actuar(secuencia, reiniciar=False), maquina.leer()) y '
                             '`import modelo` (modelo.preguntar(texto, max_tokens)), con cargo a los mismos presupuestos. El controlador '
                             'entregado puede importar lo que haya en `almacen/`, pero no `maquina` ni `modelo`.',
                             {'type': 'object', 'properties': {'codigo': {'type': 'string'}}, 'required': ['codigo']},
                             lambda codigo: m.ejecutar(codigo)))
    return h
