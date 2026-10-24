"""Corre el laboratorio B sobre un banco de secuencias (notas/diseno-simulador-b.md).

Reanudable: cada episodio hecho queda en `registro.jsonl` y no se repite. Los almacenes de LIBRE se guardan tras cada
problema (`almacenes/<secuencia>/tras_<k>`), así que la cadena se puede reanudar. Orden por secuencia:
1. construcción (por problema, todas las ramas; con RETRO, cada rama con historial lo acumula en
   `historiales/<secuencia>/<rama>` y la fuente del trasplante pasa a ser RETRO, con validar en todos los brazos);
2. informe y repertorio;
3. trasplante (por problema de prueba, todos los brazos).
Parada suave: una ronda solo empieza si quedan fondos para el tope por episodio de todo lo pendiente en la ronda.
Un episodio sin entrega o con el presupuesto agotado queda marcado como incompleto (dueño 21/10).

python -m ejecutor.maquinas_correr --banco bancos/maquinas/piloto.json --ramas FIJO,LIBRE --brazos T0,T_TODO \
    --por-episodio 0.5 --tope 5 --salida resultados/maq-xxx
"""
import argparse
import json
from pathlib import Path

from base import maquinas_ramas as R
from base import maquinas_retro as RT
from ejecutor.agente import Presupuesto
from ejecutor.laboratorio_correr import incompleto
from generadores import maquinas as G

RAMAS = ('FIJO', 'LIBRE', 'LIBRE_SIN_MEMORIA')
# factorial con retroalimentación (dueño 23/10): retro sí/no × almacén persistente sí/no
RAMAS_RETRO = ('LIBRE', 'LIBRE_SIN_MEMORIA', 'RETRO', 'RETRO_SIN_ALMACEN')


def _almacenes(base, rama):
    """Carpeta de los almacenes de una rama persistente (LIBRE conserva la disposición del piloto)."""
    return base if rama == 'LIBRE' else base / rama


def _leer(registro):
    return [json.loads(l) for l in registro.read_text().splitlines() if l.strip()] if registro.exists() else []


class Corrida:
    def __init__(self, cliente, salida, por_episodio, tope):
        self.cliente, self.salida, self.por_episodio, self.tope = cliente, Path(salida), por_episodio, tope
        self.salida.mkdir(parents=True, exist_ok=True)
        self.registro = self.salida / 'registro.jsonl'
        filas = _leer(self.registro)
        self.hechos = {(f['fase'], f['rama'], f['secuencia'], f['problema']): f for f in filas}
        self.gastado = sum(f['dolares'] for f in filas)
        self.resumen = []

    def hay_fondos(self, pendientes, que):
        if self.tope - self.gastado < self.por_episodio * pendientes:
            self.resumen.append(f'PARADA antes de {que}: quedan {self.tope - self.gastado:.2f} $ < '
                                f'{self.por_episodio * pendientes:.2f} $')
            return False
        return True

    def guardar(self, fase, rama, sec, problema, presupuesto, fila):
        fila = {'fase': fase, 'rama': rama, 'secuencia': sec, 'problema': problema, **fila,
                'dolares': round(presupuesto.gastado, 5), 'llamadas': presupuesto.llamadas,
                'interrupciones': presupuesto.interrupciones,
                'incompleto': incompleto(fila.get('controlador', True), presupuesto) if fase != 'informe' else None}
        self.gastado += presupuesto.gastado
        with self.registro.open('a') as f:
            f.write(json.dumps(fila, ensure_ascii=False, default=str) + '\n')
        self.hechos[(fase, rama, sec, problema)] = fila
        return fila


def correr(cliente, banco, ramas, brazos, por_episodio, tope, salida):
    c = Corrida(cliente, salida, por_episodio, tope)
    for s in banco:
        sid = str(s['semilla'])
        base = c.salida / 'talleres' / sid
        almacenes = c.salida / 'almacenes' / sid
        construccion = s['construccion']
        historiales = c.salida / 'historiales' / sid
        fuente = 'RETRO' if 'RETRO' in ramas else 'LIBRE'      # de quién es el almacén que se trasplanta
        # 1. construcción
        for k, p in enumerate(construccion):
            pendientes = [r for r in ramas if ('construccion', r, sid, p['semilla']) not in c.hechos]
            if not pendientes:
                continue
            if not c.hay_fondos(len(pendientes), f'{sid}/{p["semilla"]}'):
                return c.resumen, c.gastado
            prob = G.construir(p['semilla'], p['tipos'])
            for rama in pendientes:
                persistente = rama in R.PERSISTENTES
                previo = _almacenes(almacenes, rama) / f'tras_{k}' if persistente and k > 0 else None
                pres = Presupuesto(por_episodio)
                taller = base / rama / f'{k + 1}'
                fila = R.episodio(cliente, prob, rama, taller, pres, k + 1, len(construccion), previo,
                                  historial=historiales / rama)
                if persistente:
                    R.copiar_almacen(taller, _almacenes(almacenes, rama) / f'tras_{k + 1}')
                if rama in R.CON_HISTORIAL:
                    RT.anotar_historial(historiales / rama, k + 1, fila)
                c.guardar('construccion', rama, sid, p['semilla'], pres,
                          {'orden': k + 1, 'clase': 'construccion', 'tipos': p['tipos'], 'estrato': p['estrato'], **fila})
        final = _almacenes(almacenes, fuente) / f'tras_{len(construccion)}'
        necesita = set(brazos) - {'T0'}
        # 2. informe y repertorio
        if 'T_NOTAS' in necesita and ('informe', fuente, sid, '-') not in c.hechos:
            if not final.exists() or not c.hay_fondos(1, f'{sid}/informe'):
                return c.resumen, c.gastado
            resultados = [c.hechos[('construccion', fuente, sid, p['semilla'])]['puntuacion'] for p in construccion]
            pres = Presupuesto(por_episodio)
            c.guardar('informe', fuente, sid, '-', pres, R.informe(cliente, final, resultados, pres))
        if 'T_REPERTORIO' in necesita and ('repertorio', 'REPERTORIO', sid, '-') not in c.hechos:
            if not c.hay_fondos(1, f'{sid}/repertorio'):
                return c.resumen, c.gastado
            pres = Presupuesto(por_episodio)
            taller = base / 'REPERTORIO'
            fila = R.repertorio(cliente, G.construir(construccion[0]['semilla'], construccion[0]['tipos']), taller, pres)
            R.copiar_almacen(taller, almacenes / 'repertorio')
            c.guardar('repertorio', 'REPERTORIO', sid, '-', pres, {**fila, 'controlador': True})
        if ({'T_TODO', 'T_CODIGO_TEXTO', 'T_SIN_CODIGO'} & necesita) and not final.exists():
            c.resumen.append(f'{sid}: sin almacén final de {fuente}; no hay trasplante')
            continue
        texto_informe = c.hechos.get(('informe', fuente, sid, '-'), {}).get('texto', '')
        texto_historial = RT.texto_historial(historiales / fuente)
        sin_codigo = R.sin_codigo(final, almacenes / f'{fuente}_sin_codigo') if 'T_SIN_CODIGO' in necesita else None
        rama_trasplante = 'TRASPLANTE_RETRO' if fuente == 'RETRO' else 'TRASPLANTE'
        # 3. trasplante
        for clase in ('afines', 'ajenos'):
            for p in s[clase]:
                pendientes = [b for b in brazos if ('trasplante', b, sid, p['semilla']) not in c.hechos]
                if not pendientes:
                    continue
                if not c.hay_fondos(len(pendientes), f'{sid}/{p["semilla"]}'):
                    return c.resumen, c.gastado
                prob = G.construir(p['semilla'], p['tipos'])
                for brazo in pendientes:
                    almacen, extra = R.material_trasplante(brazo, final, texto_informe, almacenes / 'repertorio',
                                                           texto_historial, sin_codigo)
                    pres = Presupuesto(por_episodio)
                    fila = R.episodio(cliente, prob, rama_trasplante, base / brazo / p['semilla'], pres, 1, 1,
                                      almacen, extra)
                    c.guardar('trasplante', brazo, sid, p['semilla'], pres,
                              {'clase': clase, 'tipos': p['tipos'], 'estrato': p['estrato'], **fila})
        c.resumen.append(f'{sid}: hecha')
    return c.resumen, c.gastado


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--banco', type=Path, required=True)
    ap.add_argument('--ramas', default=','.join(RAMAS))
    ap.add_argument('--brazos', default=','.join(R.BRAZOS_TRASPLANTE))
    ap.add_argument('--por-episodio', type=float, required=True)
    ap.add_argument('--tope', type=float, required=True)
    ap.add_argument('--salida', type=Path, required=True)
    a = ap.parse_args()
    import os
    import anthropic
    from .clave import cargar_clave
    cargar_clave()
    espacio = os.environ.get('ANTHROPIC_WORKSPACE_ID')
    cliente = anthropic.Anthropic(max_retries=4, default_headers={'anthropic-workspace-id': espacio} if espacio else None)
    brazos = [b for b in a.brazos.split(',') if b]
    resumen, gastado = correr(cliente, json.loads(a.banco.read_text()), a.ramas.split(','), brazos, a.por_episodio,
                              a.tope, a.salida)
    print('\n'.join(resumen))
    print(f'gastado en {a.salida}: {gastado:.2f} $')


if __name__ == '__main__':
    main()
