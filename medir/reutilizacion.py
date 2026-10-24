"""Reutilización de código heredado más allá de importar o ejecutar (dueño 23/10, tras el piloto con
retroalimentación): una instancia que copia un programa heredado, lo modifica y valida la versión nueva también lo
reutiliza, y la métrica anterior no lo veía.

Niveles por episodio, frente a los ficheros `.py` heredados (de mayor a menor):
- ejecuta: importa o ejecuta un fichero heredado (métrica corregida del 23/10, `medir.maquinas.usos` funcional);
- copia: algún controlador validado o entregado coincide casi entero con un heredado distintivo (cobertura ≥ LITERAL);
- adapta: coincide en buena parte con uno distintivo (UMBRAL ≤ cobertura < LITERAL);
- indistinguible: coincide con un heredado que las ramas sin acceso también reproducen (no se puede saber si lo copió);
- abre: solo lee algún heredado que ya estaba en su almacén al empezar;
- ninguno.

Cobertura: fracción de los símbolos del controlador cubierta por bloques comunes de al menos BLOQUE símbolos con un
fichero heredado. Sin comentarios, y con números y cadenas sustituidos por N y S, para que cambiar constantes, también
de signo, cuente como copiar.

Línea base: el mismo modelo escribe controladores parecidos sin ver nada. Un controlador integral corto lo reescribe
casi igual una instancia que nunca lo vio, y uno largo no. Por eso se mide, en la misma corrida, la cobertura que
alcanzan contra cada fichero las ramas sin acceso a él (`nulo_por_fichero`). Un fichero es distintivo si esa cobertura
nula se queda por debajo de DISTINTIVO; solo contra los distintivos se cuenta copia o adaptación.

Nada de esto mide contribución causal: eso solo lo dan los brazos de ablación y la comparación emparejada con T0.

python -m medir.reutilizacion <resultados> [secuencia]
"""
import difflib
import io
import json
import sys
import tokenize
from collections import defaultdict
from pathlib import Path

from medir import maquinas as M

BLOQUE = 12
UMBRAL = 0.85
LITERAL = 0.97
DISTINTIVO = 0.5   # piloto: nula ≤ 0,34 en los ficheros largos y 0,61–0,83 en los integrales cortos
# ramas que nunca vieron el código de RETRO; T_SIN_CODIGO no entra: sus notas lo describen (lo reconstruye hasta 0,47)
SIN_ACCESO = ('T0', 'T_HISTORIAL', 'LIBRE', 'LIBRE_SIN_MEMORIA', 'RETRO_SIN_ALMACEN')
TRAS_UNARIO = {'(', '[', '{', ',', '=', ':', 'return', '+', '-', '*', '/', '@', '<', '>', '==', '<=', '>=', '+=', '-=',
               '*=', 'and', 'or', 'not', 'if', 'else', 'in', 'lambda'}


def simbolos(codigo):
    salida = []
    try:
        for t in tokenize.generate_tokens(io.StringIO(codigo).readline):
            if t.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
                          tokenize.ENDMARKER):
                continue
            if t.type == tokenize.NUMBER and salida[-1:] in (['-'], ['+']) and \
                    (len(salida) < 2 or salida[-2] in TRAS_UNARIO):
                salida.pop()      # el signo de una constante es parte de la constante
            salida.append('N' if t.type == tokenize.NUMBER else 'S' if t.type == tokenize.STRING else t.string)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return salida


def cobertura(codigo, heredado):
    c, h = simbolos(codigo), simbolos(heredado)
    sm = difflib.SequenceMatcher(None, c, h, autojunk=False)
    return sum(b.size for b in sm.get_matching_blocks() if b.size >= BLOQUE) / max(1, len(c))


def candidatos(f, taller):
    """Código que contó en el episodio: lo entregado y la versión final de cada fichero validado."""
    salida = [('entrega', f['codigo_entregado'])] if f.get('codigo_entregado') else []
    for v in f.get('validaciones', []):
        p = Path(taller) / v['ruta']
        if p.is_file() and v['ruta'] not in [n for n, _ in salida]:
            salida.append((v['ruta'], p.read_text()))
    return salida


def mejor(f, taller, heredados):
    """(cobertura máxima, fichero heredado) del episodio."""
    return max(((cobertura(c, h), n) for _, c in candidatos(f, taller) for n, h in heredados.items()),
               default=(0.0, None))


def nivel(f, taller, heredados, distintivos=None):
    """(nivel, cobertura, fichero heredado). `distintivos`: ficheros contra los que se puede contar copia (None: todos)."""
    distintivos = set(heredados) if distintivos is None else set(distintivos)
    cob, fuente = mejor(f, taller, {n: h for n, h in heredados.items() if n in distintivos})
    if any(Path(u).name in heredados for u in M.usos(f, funcional=True)):
        return 'ejecuta', cob, fuente
    if cob >= LITERAL:
        return 'copia', cob, fuente
    if cob >= UMBRAL:
        return 'adapta', cob, fuente
    cob_comun, comun = mejor(f, taller, {n: h for n, h in heredados.items() if n not in distintivos})
    if cob_comun >= UMBRAL:
        return 'indistinguible', cob_comun, comun
    if {Path(u).name for u in M.usos(f)} & set(heredados):
        return 'abre', cob, fuente
    return 'ninguno', cob, fuente


def heredados_de(carpeta):
    return {p.name: p.read_text() for p in sorted(Path(carpeta).glob('*.py'))} if Path(carpeta).exists() else {}


def episodios(r, sec):
    """(fila, taller, heredados de RETRO que le corresponden) de cada episodio de la secuencia. En construcción, el
    almacén de RETRO tras el problema anterior; en trasplante, el final. Las ramas sin acceso se miden igual: son la
    línea base."""
    r = Path(r)
    filas = [json.loads(l) for l in (r / 'registro.jsonl').read_text().splitlines()]
    filas = [f for f in filas if f['secuencia'] == sec]
    n_cons = max([f['orden'] for f in filas if f['fase'] == 'construccion'], default=0)
    for f in filas:
        if f['fase'] == 'construccion':
            if f['orden'] == 1:
                continue
            taller = r / 'talleres' / sec / f['rama'] / str(f['orden'])
            her = heredados_de(r / 'almacenes' / sec / 'RETRO' / f'tras_{f["orden"] - 1}')
        else:
            taller = r / 'talleres' / sec / f['rama'] / f['problema']
            her = heredados_de(r / 'almacenes' / sec / 'RETRO' / f'tras_{n_cons}')
        yield f, taller, her


def nulo_por_fichero(eps):
    """Cobertura máxima que alcanzan contra cada fichero heredado las ramas sin acceso a él."""
    salida = defaultdict(float)
    for f, t, her in eps:
        if f['rama'] in SIN_ACCESO:
            for n, h in her.items():
                salida[n] = max([salida[n]] + [cobertura(c, h) for _, c in candidatos(f, t)])
    return dict(salida)


def main():
    r = Path(sys.argv[1])
    sec = sys.argv[2] if len(sys.argv) > 2 else '200'
    eps = list(episodios(r, sec))
    nulo = nulo_por_fichero(eps)
    distintivos = {n for n, x in nulo.items() if x < DISTINTIVO}
    n_nulo = sum(f['rama'] in SIN_ACCESO for f, _, _ in eps)
    print(f'Línea base: cobertura máxima de las ramas sin acceso ({n_nulo} episodios) contra cada fichero heredado:')
    for n, x in sorted(nulo.items(), key=lambda e: e[1]):
        print(f'  {n}: {x:.2f} ({"distintivo" if n in distintivos else "no distintivo"})')
    for fase in ('construccion', 'trasplante'):
        print(f'\n{fase}: rama | problema | clase | cumplido | nivel | cobertura | fuente')
        resumen = defaultdict(lambda: defaultdict(list))
        for f, t, h in sorted(eps, key=lambda e: (e[0]['rama'], e[0].get('orden', 0), e[0]['problema'])):
            if f['fase'] != fase:
                continue
            nv, cob, fuente = nivel(f, t, h, distintivos)
            resumen[f['rama']][nv].append(M.cumplido(f))
            print(f'  {f["rama"]} | {f["problema"]} | {f["clase"]} | {"sí" if M.cumplido(f) else "no"}'
                  f'{" (incompleto)" if f.get("incompleto") else ""} | {nv} | {cob:.2f} | {fuente or "—"}')
        print(f'  resumen {fase} (nivel: episodios, cumplidos):')
        for rama, niveles in sorted(resumen.items()):
            print(f'    {rama}: ' + '; '.join(f'{nv} {len(c)}, {sum(c)}' for nv, c in sorted(niveles.items())))


if __name__ == '__main__':
    main()
