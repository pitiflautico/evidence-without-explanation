"""Corre las ramas del laboratorio de organización sobre una lista de problemas (notas/diseno-organizacion.md).

Reanudable: cada episodio hecho queda en `registro.jsonl` y no se repite. Orden por problema (todas las ramas del
problema 1, luego las del 2…): si el tope corta, todas las ramas llevan los mismos problemas. Parada suave: un
problema solo empieza si quedan fondos para el tope por episodio de todas las ramas pendientes.

python -m ejecutor.laboratorio_correr --ramas A,A_ext,B,X --problemas bancos/laboratorio/desarrollo.json \
    --por-episodio 1.0 --tope 10 --salida resultados/lab-xxx
"""
import argparse
import json
from pathlib import Path

from base.necesidades import RAMAS_NEC
from base.organizacion import RAMAS_LAB
from ejecutor.agente import Presupuesto
from generadores import laboratorio as L


def _leer(registro):
    return [json.loads(l) for l in registro.read_text().splitlines() if l.strip()] if registro.exists() else []


def incompleto(solucion, presupuesto):
    """Episodio cortado (dueño 21/10): sin entrega, o algún agente se quedó sin presupuesto por episodio."""
    motivos = [m for _, m in presupuesto.interrupciones if m == 'presupuesto agotado']
    return 'sin entrega' if solucion is None else ('presupuesto agotado' if motivos else None)


def correr(cliente, ramas, problemas, por_episodio, tope, salida):
    salida.mkdir(parents=True, exist_ok=True)
    registro = salida / 'registro.jsonl'
    hechos = {(f['rama'], f['problema']) for f in _leer(registro)}
    gastado = sum(f['dolares'] for f in _leer(registro))
    resumen = []
    for familia, semilla in problemas:
        pid = f'{familia}-{semilla}'
        pendientes = [r for r in ramas if (r, pid) not in hechos]
        if not pendientes:
            continue
        if tope - gastado < por_episodio * len(pendientes):
            resumen.append(f'PARADA antes de {pid}: quedan {tope - gastado:.2f} $ < '
                           f'{por_episodio * len(pendientes):.2f} $ para la ronda')
            return resumen, gastado
        prob = L.construir(familia, semilla)
        for rama in pendientes:
            presupuesto = Presupuesto(por_episodio)
            salida_rama = {**RAMAS_LAB, **RAMAS_NEC}[rama](cliente, prob, presupuesto)
            ev = L.evaluar(prob, salida_rama['solucion'])
            fila = {'rama': rama, 'problema': pid, 'familia': familia, 'semilla': semilla,
                    'entregado': salida_rama['solucion'] is not None, **ev,
                    'incompleto': incompleto(salida_rama['solucion'], presupuesto),
                    'solucion': salida_rama['solucion'], 'dolares': round(presupuesto.gastado, 5),
                    'interrupciones': presupuesto.interrupciones, 'llamadas': presupuesto.llamadas,
                    'estructura': salida_rama['estructura']}
            gastado += presupuesto.gastado
            with registro.open('a') as f:
                f.write(json.dumps(fila, ensure_ascii=False, default=str) + '\n')
        resumen.append(f'{pid}: {len(pendientes)} ramas')
    return resumen, gastado


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ramas', required=True)
    ap.add_argument('--problemas', type=Path, required=True, help='JSON [[familia, semilla], ...]')
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
    resumen, gastado = correr(cliente, a.ramas.split(','), json.loads(a.problemas.read_text()), a.por_episodio,
                              a.tope, a.salida)
    print('\n'.join(resumen))
    print(f'gastado en {a.salida}: {gastado:.2f} $')


if __name__ == '__main__':
    main()
