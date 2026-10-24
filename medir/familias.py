"""Familias funcionales de controladores (notas/diseno-a-aplus-x.md §5.1; fijado antes de correr ningún brazo).

Medida secundaria, por código. Dos controladores son de la misma familia si tienen la misma firma funcional, y una
variante (otros parámetros u otro programa) no cambia la firma. La firma se mide sondeando el controlador en el
taller aislado, nunca leyendo su texto:
- memoria: con la misma lectura final, dos historias distintas dan acciones distintas (> TOL);
- no_lineal: falla la superposición de las respuestas a pequeñas desviaciones de las lecturas (amplitudes PEQUENA y
  GRANDE alrededor de cero), sin contar las acciones que tocan el límite de los actuadores;
- conmuta: barriendo una lectura en pasos de BARRIDO, la acción salta entre dos puntos vecinos más de SALTO y más de
  VECES la mediana de los cambios no nulos entre vecinos (lógica discreta: ramas, regímenes, umbrales; un recorte o un codo no
  es un salto).
Las sondas se centran en el objetivo del problema (`centro`): lejos de él, un controlador puede quedarse en el límite
de los actuadores y esconder su forma.

Limitaciones declaradas: un recorte del error es «no lineal» aunque solo sea un ajuste de robustez, y una explicación
nueva que no cambie estas tres propiedades no se detecta. Por eso la medida principal de la diversidad de
explicaciones es la auditoría ciega de las conversaciones (§5.1 del diseño), y esta solo la complementa.
"""
import tempfile
from pathlib import Path

from base import maquinas_entorno as E
from ejecutor.agente import Presupuesto
from generadores import maquinas as G

TOL = 1e-3
PEQUENA, GRANDE = 0.1, 1.0
BARRIDO, SALTO, VECES = 0.05, 0.05, 10
LARGO = 12                       # pasos de cada sonda
TOPE = G.LIMITE - 0.01


_VIVAS = []                      # el controlador aislado reinicia la memoria cuando cambia id(memoria): no reutilizar ids


def _respuesta(c, secuencia):
    memoria = {}
    _VIVAS.append(memoria)
    salida = None
    for lec in secuencia:
        salida = [float(a) for a in c(list(lec), memoria)]
    return salida


def firma(c, centro):
    """{'memoria', 'no_lineal', 'conmuta'} de un controlador c(lecturas, memoria) -> acciones, alrededor de `centro`."""
    mas = lambda d: [o + x for o, x in zip(centro, d)]
    base = _respuesta(c, [list(centro)] * LARGO)
    otra = _respuesta(c, [mas([0.5] * G.N_CAN)] * (LARGO - 1) + [list(centro)])
    memoria = any(abs(a - b) > TOL for a, b in zip(base, otra))
    no_lineal = False
    for amp in (PEQUENA, GRANDE):
        # las dos sondas actúan en los dos canales (con una por canal, un controlador desacoplado siempre superpone) y
        # no tienen media cero (un integrador suma una sonda simétrica a cero y esconde un recorte simétrico)
        d1 = [[amp * (t % 3) / 2] * G.N_CAN for t in range(LARGO)]
        d2 = [[amp * (t % 2) * (-1) ** i for i in range(G.N_CAN)] for t in range(LARGO)]
        r1, r2 = _respuesta(c, [mas(x) for x in d1]), _respuesta(c, [mas(x) for x in d2])
        r12 = _respuesta(c, [mas([a + b for a, b in zip(x, y)]) for x, y in zip(d1, d2)])
        if any(abs(v) >= TOPE for v in base + r1 + r2 + r12):
            continue
        tol = TOL + 0.02 * max(abs(v) for v in r1 + r2 + r12 + [1e-9])
        no_lineal |= any(abs((v12 - b) - ((v1 - b) + (v2 - b))) > tol for v12, v1, v2, b in zip(r12, r1, r2, base))
    conmuta = False
    for canal in range(G.N_CAN):
        us = []
        for i in range(int(2 * G.LIMITE / BARRIDO) + 1):
            lec = list(centro)
            lec[canal] = -G.LIMITE + i * BARRIDO
            us.append(_respuesta(c, [lec] * 3))
        for j in range(G.N_ACT):
            cambios = sorted(abs(a[j] - b[j]) for a, b in zip(us[1:], us[:-1]))
            moviles = [x for x in cambios if x > TOL] or [0.0]          # sin los tramos planos (límite, recorte)
            mediana = moviles[len(moviles) // 2]
            conmuta |= cambios[-1] > max(SALTO, VECES * mediana)
    return {'memoria': memoria, 'no_lineal': no_lineal, 'conmuta': conmuta}


def firma_codigo(codigo, centro):
    """Firma de un controlador dado como texto, sondeado en un taller aislado temporal."""
    with tempfile.TemporaryDirectory() as tmp:
        m = E.Mundo(G.construir('firma', []), Path(tmp) / 'taller', Presupuesto(maximo=0))
        (m.taller / 'c.py').write_text(codigo)
        c = m.controlador('c.py')
        try:
            f = firma(c, centro)
        finally:
            c.cerrar()
            _VIVAS.clear()
        if c.error:
            return {'error': c.error}
        return f


def familias(codigos, centro):
    """Número de firmas distintas entre los controladores de un episodio (validados y entregado), en orden."""
    firmas = [firma_codigo(x, centro) for x in codigos]
    vistas = []
    for f in firmas:
        if 'error' not in f and f not in vistas:
            vistas.append(f)
    return {'firmas': firmas, 'distintas': len(vistas)}
