"""Lectura del piloto A / A_PISTA / A+ / X (notas/diseno-a-aplus-x.md §5 y §11). Sin gasto.

python -m medir.hipotesis_piloto principales resultados/hipotesis-piloto
python -m medir.hipotesis_piloto exportar resultados/hipotesis-piloto <carpeta_ciega> <clave.json>
python -m medir.hipotesis_piloto cruzar resultados/hipotesis-piloto <carpeta_ciega> <clave.json>
python -m medir.hipotesis_piloto firmas resultados/hipotesis-piloto

- principales: cumplidos, dólares y CPU por brazo, emparejados por problema; uso de `contraste` y de los contextos.
- exportar: cada conversación a texto, sin el nombre del brazo y en orden aleatorio, para la auditoría de familias
  (§5.1). Se quitan los párrafos del enunciado propios de cada brazo; el uso de `contraste` o de `abrir_contexto` sigue
  delatando A+ y X (ciego parcial, declarado). La clave (código → problema y brazo) se guarda aparte.
- firmas: medida secundaria (§5.1), firmas funcionales distintas entre los controladores validados y el entregado.
- cruzar: une la clasificación (`<código>.json` en la carpeta ciega, escrita por el auditor) con la clave y calcula
  familias por episodio, salida de familia tras cada validación fallida y generación de la familia del fallo.
"""
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

from base import maquinas_hipotesis as H

UMBRAL = 0.9
CORTE_RESULTADO = 1500
FAMILIA_DE = {'retardo': 'F1', 'acumulador': 'F1', 'saturacion': 'F2', 'modo': 'F3', 'histeresis': 'F4',
              'deriva': 'F5', 'aliasing': 'F6'}


def _filas(carpeta):
    return [json.loads(l) for l in (Path(carpeta) / 'registro.jsonl').read_text().splitlines() if l.strip()]


def _usa_contraste(conv):
    return sum('contrastar(' in json.dumps(b.get('input', {}), ensure_ascii=False)
               for m in conv['conversacion'] if m['role'] == 'assistant' and isinstance(m['content'], list)
               for b in m['content'] if b.get('type') == 'tool_use')


def principales(carpeta):
    carpeta = Path(carpeta)
    filas = _filas(carpeta)
    por = defaultdict(dict)
    for f in filas:
        por[f['problema']][f['brazo']] = f
    completos = [p for p, d in por.items() if len(d) == len(H.BRAZOS)]
    lineas = [f'Episodios: {len(filas)}; problemas con los {len(H.BRAZOS)} brazos: {len(completos)}; '
              f'gasto {sum(f["dolares"] for f in filas):.2f} $', '',
              'brazo | cumplidos | puntuación media | dólares | $ por cumplido | CPU código (s) | sin entrega | '
              'usa contraste | contextos abiertos']
    for b in H.BRAZOS:
        fs = [por[p][b] for p in completos]
        cum = sum(f['puntuacion'] >= UMBRAL for f in fs)
        dol = sum(f['dolares'] for f in fs)
        usos = [_usa_contraste(json.loads((carpeta / 'conversaciones' / f['problema'] / f'{b}.json').read_text()))
                for f in fs]
        lineas.append(f'{b} | {cum} de {len(fs)} | {sum(f["puntuacion"] for f in fs) / len(fs):.3f} | {dol:.2f} | '
                      f'{dol / cum if cum else float("inf"):.2f} | {sum(f["cpu_codigo"] for f in fs):.1f} | '
                      f'{sum(not f["entregado"] for f in fs)} | {sum(u > 0 for u in usos)} episodios '
                      f'({sum(usos)} llamadas) | {sum(len(f["contextos"]) for f in fs)}')
    lineas += ['', 'problema | ' + ' | '.join(H.BRAZOS)]
    lineas += [f'{p} | ' + ' | '.join(f'{por[p][b]["puntuacion"]:.3f}' for b in H.BRAZOS) for p in completos]
    lineas += ['', 'Emparejado frente a A (problemas en que el brazo puntúa más / menos / igual):']
    for b in H.BRAZOS[1:]:
        d = [por[p][b]['puntuacion'] - por[p]['A']['puntuacion'] for p in completos]
        lineas.append(f'{b} − A: más {sum(x > 1e-9 for x in d)}, menos {sum(x < -1e-9 for x in d)}, igual '
                      f'{sum(abs(x) <= 1e-9 for x in d)}; diferencia media {sum(d) / len(d):+.3f}')
    return lineas


def _limpiar_enunciado(texto):
    for parrafo in (H.PISTA, H.MODULO):
        texto = texto.replace(parrafo, '')
    return texto


def _texto_entrada(nombre, entrada):
    if nombre == 'actuar':
        s = entrada.get('secuencia', [])
        return f'actuar({len(s)} pasos, reiniciar={entrada.get("reiniciar", False)}): {json.dumps(s)[:300]}'
    if 'codigo' in entrada:
        return f'{nombre}:\n{entrada["codigo"]}'
    return f'{nombre}({json.dumps(entrada, ensure_ascii=False)})'


def texto_conversacion(conv):
    """La conversación como texto con turnos numerados (turno = respuesta del modelo)."""
    salida = ['ENUNCIADO:', _limpiar_enunciado(conv['enunciado']), '']
    turno = 0
    for m in conv['conversacion'][1:]:
        if m['role'] == 'assistant':
            turno += 1
            salida.append(f'=== TURNO {turno} (modelo) ===')
            for b in m['content'] if isinstance(m['content'], list) else [{'type': 'text', 'text': m['content']}]:
                if b.get('type') == 'text' and b.get('text'):
                    salida.append(b['text'])
                elif b.get('type') == 'tool_use':
                    salida.append('[herramienta] ' + _texto_entrada(b['name'], b.get('input', {})))
        else:
            for b in m['content'] if isinstance(m['content'], list) else [{'type': 'text', 'text': m['content']}]:
                c = b.get('content', b.get('text', ''))
                c = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
                salida.append(f'[resultado] {c[:CORTE_RESULTADO]}' + (' […]' if len(c) > CORTE_RESULTADO else ''))
    if conv.get('texto_final'):
        salida += ['=== TEXTO FINAL ===', conv['texto_final']]
    for c in conv.get('contextos', []):
        salida += [f'=== CONTEXTO {c["n"]} (otra instancia; encargo) ===', c['encargo'],
                   texto_conversacion({'enunciado': '', 'conversacion': [None] + c['conversacion'][1:],
                                       'texto_final': c.get('texto_final'), 'contextos': []})]
    return '\n'.join(salida)


def exportar(carpeta, ciega, clave, semilla='ciego-axe'):
    carpeta, ciega = Path(carpeta), Path(ciega)
    ciega.mkdir(parents=True, exist_ok=True)
    episodios = sorted((f['problema'], f['brazo']) for f in _filas(carpeta))
    random.Random(semilla).shuffle(episodios)
    mapa = {}
    for k, (p, b) in enumerate(episodios, 1):
        codigo = f'e{k:02d}'
        conv = json.loads((carpeta / 'conversaciones' / p / f'{b}.json').read_text())
        (ciega / f'{codigo}.txt').write_text(texto_conversacion(conv))
        mapa[codigo] = {'problema': p, 'brazo': b}
    Path(clave).write_text(json.dumps(mapa, indent=1))
    return len(mapa)


def _validaciones_turnos(conv):
    """Turnos (del modelo) en que valida o entrega, en orden: [(turno, 'validar'|'entregar')]."""
    turno, eventos = 0, []
    for m in conv['conversacion'][1:]:
        if m['role'] == 'assistant':
            turno += 1
            for b in m['content'] if isinstance(m['content'], list) else []:
                if b.get('type') == 'tool_use' and b['name'] in ('validar', 'entregar'):
                    eventos.append((turno, b['name']))
    return eventos


def cruzar(carpeta, ciega, clave):
    """Clasificación del auditor: {'afirmaciones': [{'turno', 'familia', 'cita'}]} por episodio."""
    carpeta, ciega = Path(carpeta), Path(ciega)
    mapa = json.loads(Path(clave).read_text())
    filas = {(f['problema'], f['brazo']): f for f in _filas(carpeta)}
    por_brazo = defaultdict(list)
    for codigo, e in sorted(mapa.items()):
        cls = json.loads((ciega / f'{codigo}.json').read_text())
        f = filas[(e['problema'], e['brazo'])]
        conv = json.loads((carpeta / 'conversaciones' / e['problema'] / f'{e["brazo"]}.json').read_text())
        primera = {}
        for a in sorted(cls['afirmaciones'], key=lambda a: a['turno']):
            primera.setdefault(a['familia'], a['turno'])
        eventos = _validaciones_turnos(conv)
        # salida de familia: tras cada validación fallida, ¿aparece una familia nueva antes del siguiente validar/entregar?
        fallidas, salidas = 0, 0
        for i, v in enumerate(f['validaciones']):
            if v['cumplidos'] / len(v['fracciones']) >= UMBRAL or i >= len([x for x in eventos if x[1] == 'validar']):
                continue
            t0 = [x for x in eventos if x[1] == 'validar'][i][0]
            siguientes = [t for t, _ in eventos if t > t0]
            if not siguientes:
                continue
            fallidas += 1
            salidas += any(t0 < t <= siguientes[0] for t in primera.values())
        verdad = {FAMILIA_DE[t] for t in f['tipos']}
        por_brazo[e['brazo']].append({'problema': e['problema'], 'familias': sorted(primera, key=primera.get),
                                      'n_familias': len([x for x in primera if x != 'F0']),
                                      'fallidas_con_continuacion': fallidas, 'salidas': salidas,
                                      'verdaderas_planteadas': len(verdad & set(primera)), 'verdaderas': len(verdad),
                                      'puntuacion': f['puntuacion']})
    lineas = ['brazo | familias distintas por episodio (sin F0) | salidas de familia / validaciones fallidas | '
              'familias verdaderas planteadas / presentes']
    for b in H.BRAZOS:
        es = por_brazo[b]
        lineas.append(f'{b} | {sum(x["n_familias"] for x in es) / len(es):.2f} | '
                      f'{sum(x["salidas"] for x in es)} / {sum(x["fallidas_con_continuacion"] for x in es)} | '
                      f'{sum(x["verdaderas_planteadas"] for x in es)} / {sum(x["verdaderas"] for x in es)}')
    lineas += ['', 'brazo | problema | familias en orden de aparición | puntuación']
    lineas += [f'{b} | {x["problema"]} | {",".join(x["familias"])} | {x["puntuacion"]:.3f}'
               for b in H.BRAZOS for x in sorted(por_brazo[b], key=lambda x: x['problema'])]
    return lineas, por_brazo


def firmas(carpeta):
    from generadores import maquinas as G
    from medir import familias as FA
    lineas, por_brazo = ['brazo | problema | controladores | firmas distintas | firmas en orden'], defaultdict(list)
    for f in _filas(carpeta):
        codigos = list(f['controladores_validados'].values())
        if f['codigo_entregado'] and f['codigo_entregado'] not in codigos:
            codigos.append(f['codigo_entregado'])
        r = FA.familias(codigos, G.construir(f['problema'], f['tipos'])['objetivo'])
        por_brazo[f['brazo']].append(r['distintas'])
        orden = ['error' if 'error' in x else '+'.join(k for k, v in x.items() if v) or 'lineal_sin_memoria'
                 for x in r['firmas']]
        lineas.append(f'{f["brazo"]} | {f["problema"]} | {len(codigos)} | {r["distintas"]} | {"; ".join(orden)}')
    lineas += [''] + [f'{b}: firmas distintas por episodio {sum(v) / len(v):.2f}; episodios con más de una '
                      f'{sum(x > 1 for x in v)} de {len(v)}' for b, v in por_brazo.items()]
    return lineas


def main():
    orden, carpeta = sys.argv[1], sys.argv[2]
    if orden == 'principales':
        print('\n'.join(principales(carpeta)))
    elif orden == 'exportar':
        print(f'{exportar(carpeta, sys.argv[3], sys.argv[4])} conversaciones exportadas')
    elif orden == 'firmas':
        print('\n'.join(firmas(carpeta)))
    elif orden == 'cruzar':
        print('\n'.join(cruzar(carpeta, sys.argv[3], sys.argv[4])[0]))


if __name__ == '__main__':
    main()
