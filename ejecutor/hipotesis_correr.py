"""Corre la comparación A / A_PISTA / A+ / X sobre un banco de problemas sueltos (notas/diseno-a-aplus-x.md).

- Reanudable: cada episodio hecho queda en `registro.jsonl` y no se repite. Las conversaciones, aparte, en
  `conversaciones/<problema>/<brazo>.json` (son grandes).
- Por problema, los cuatro brazos en un orden que rota de un problema al siguiente.
- Mismo tope de dólares por episodio para todos (los contextos de X cuentan dentro). Parada automática: un episodio
  solo empieza si lo que queda del tope total cubre su tope por episodio.

python -m ejecutor.hipotesis_correr congelar --semilla axp --n 10 --banco bancos/maquinas/hipotesis.json
python -m ejecutor.hipotesis_correr congelar --semilla axe --n 10 --con-aliasing 7 --banco bancos/maquinas/hipotesis_equilibrado.json
python -m ejecutor.hipotesis_correr correr --banco bancos/maquinas/hipotesis.json --por-episodio 0.6 --tope 10 \
    --salida resultados/hipotesis-piloto
python -m ejecutor.hipotesis_correr correr --banco bancos/maquinas/hipotesis_equilibrado.json --brazos A \
    --esfuerzo high --por-episodio 0.6 --tope 4 --salida resultados/hipotesis-esfuerzo
"""
import argparse
import hashlib
import json
from pathlib import Path

from base import maquinas_hipotesis as H
from ejecutor.agente import Presupuesto
from ejecutor.laboratorio_correr import incompleto
from generadores import maquinas as G


def _leer(registro):
    return [json.loads(l) for l in registro.read_text().splitlines() if l.strip()] if registro.exists() else []


def orden(k, brazos):
    return list(brazos[k % len(brazos):]) + list(brazos[:k % len(brazos)])


def comparar_grupos(banco, margen=0.15, maximo=0.5):
    """Dificultad con y sin aliasing (§11 del diseño): (líneas del informe, si el criterio se cumple)."""
    grupos = {g: [p for p in banco if ('aliasing' in p['tipos']) == g] for g in (True, False)}
    lineas = ['problema | aliasing | tipos | ideal | ingenuo | generico | d']
    lineas += [f'{p["semilla"]} | {"sí" if g else "no"} | {",".join(p["tipos"])} | {p["ideal"]:.3f} | '
               f'{p["ingenuo"]:.3f} | {p["generico"]:.3f} | {H.dificultad(p):.3f}' for g in (True, False) for p in grupos[g]]
    media = {}
    for g, ps in grupos.items():
        ds = [H.dificultad(p) for p in ps]
        media[g] = sum(ds) / len(ds) if ds else 0.0
        no_lin = [len([t for t in p['tipos'] if t in G.NO_LINEALES]) for p in ps]
        lineas.append(f'{"con" if g else "sin"} aliasing: {len(ps)} problemas; d media {media[g]:.3f} (máx. '
                      f'{max(ds, default=0):.3f}); ideal medio {sum(p["ideal"] for p in ps) / max(len(ps), 1):.3f}; '
                      f'no lineales por problema {sum(no_lin) / max(len(ps), 1):.2f}; con lineal acompañante '
                      f'{sum(any(t in G.LINEALES for t in p["tipos"]) for p in ps)}')
    ok = media[False] - media[True] <= margen and all(H.dificultad(p) <= maximo for p in grupos[False])
    lineas.append(f'diferencia de d media (sin − con): {media[False] - media[True]:+.3f}; criterio (≤ {margen} y ningún '
                  f'problema sin aliasing con d > {maximo}): {"se cumple" if ok else "NO se cumple"}')
    return lineas, ok


def correr(cliente, banco, brazos, por_episodio, tope, salida, esfuerzo=None):
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    registro = salida / 'registro.jsonl'
    filas = _leer(registro)
    hechos = {(f['problema'], f['brazo']) for f in filas}
    gastado = sum(f['dolares'] for f in filas)
    resumen = []
    for k, p in enumerate(banco):
        prob = G.construir(p['semilla'], p['tipos'])
        for brazo in orden(k, brazos):
            if (p['semilla'], brazo) in hechos:
                continue
            if tope - gastado < por_episodio:
                resumen.append(f'PARADA antes de {p["semilla"]}/{brazo}: quedan {tope - gastado:.2f} $ < {por_episodio:.2f} $')
                return resumen, gastado
            pres = Presupuesto(por_episodio) if esfuerzo is None else Presupuesto(por_episodio, esfuerzo=esfuerzo)
            fila = H.episodio(cliente, prob, brazo, salida / 'talleres' / p['semilla'] / brazo, pres)
            conv = {'enunciado': fila.pop('enunciado'), 'conversacion': fila.pop('conversacion'),
                    'texto_final': fila.pop('texto_final'),
                    'contextos': [{**c} for c in fila['contextos']]}
            fila['contextos'] = [{x: c[x] for x in ('n', 'encargo', 'respuesta', 'turnos', 'agotado')} for c in fila['contextos']]
            destino = salida / 'conversaciones' / p['semilla']
            destino.mkdir(parents=True, exist_ok=True)
            (destino / f'{brazo}.json').write_text(json.dumps(conv, ensure_ascii=False, default=str))
            fila = {'problema': p['semilla'], 'tipos': p['tipos'], 'orden': k + 1, 'esfuerzo': pres.esfuerzo, **fila,
                    'dolares': round(pres.gastado, 5), 'llamadas': pres.llamadas, 'interrupciones': pres.interrupciones,
                    'incompleto': incompleto(fila['controlador'], pres)}
            gastado += pres.gastado
            with registro.open('a') as f:
                f.write(json.dumps(fila, ensure_ascii=False, default=str) + '\n')
            hechos.add((p['semilla'], brazo))
    resumen.append('hecha')
    return resumen, gastado


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('orden', choices=('congelar', 'correr'))
    ap.add_argument('--banco', type=Path, required=True)
    ap.add_argument('--semilla', default='axp')
    ap.add_argument('--n', type=int, default=10)
    ap.add_argument('--con-aliasing', type=int)
    ap.add_argument('--tope-d', type=float)
    ap.add_argument('--brazos', default=','.join(H.BRAZOS))
    ap.add_argument('--por-episodio', type=float)
    ap.add_argument('--tope', type=float)
    ap.add_argument('--salida', type=Path)
    ap.add_argument('--esfuerzo', help='esfuerzo del modelo (por defecto, el de ejecutor.agente)')
    a = ap.parse_args()
    if a.orden == 'congelar':
        if a.banco.exists():
            raise SystemExit(f'{a.banco} ya existe: un banco congelado no se regenera')
        b = H.banco(a.semilla, a.n, con_aliasing=a.con_aliasing, tope_d=a.tope_d)
        if a.con_aliasing is not None:
            lineas, ok = comparar_grupos(b)
            print('\n'.join(lineas))
            if not ok:
                raise SystemExit('dificultad no comparable entre grupos: no se congela (§11: regla de reserva)')
        a.banco.write_text(json.dumps(b, ensure_ascii=False, indent=1) + '\n')
        a.banco.chmod(0o444)
        print(f'{a.banco}: {a.n} problemas; sha256 {hashlib.sha256(a.banco.read_bytes()).hexdigest()}')
        return
    import os
    import anthropic
    from .clave import cargar_clave
    cargar_clave()
    espacio = os.environ.get('ANTHROPIC_WORKSPACE_ID')
    cliente = anthropic.Anthropic(max_retries=4, default_headers={'anthropic-workspace-id': espacio} if espacio else None)
    resumen, gastado = correr(cliente, json.loads(a.banco.read_text()), a.brazos.split(','), a.por_episodio, a.tope,
                              a.salida, a.esfuerzo)
    print('\n'.join(resumen))
    print(f'gastado en {a.salida}: {gastado:.2f} $')


if __name__ == '__main__':
    main()
