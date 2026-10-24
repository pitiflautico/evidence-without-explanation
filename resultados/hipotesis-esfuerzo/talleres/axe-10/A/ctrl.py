
import numpy as np
C = np.array([1.640, -0.003])
B = np.array([[1.281, -0.561], [-1.001, -1.229]])
BI = np.linalg.inv(B)
JUMP = 2.32
TGT = np.array([-0.30, 0.54])
TGT_LOW = np.array([0.3, 0.54])   # aim when in low mode (forces exit)
DELAY = 4      # reading at call k reflects action k-DELAY
ALPHA = 0.5

def controlar(lecturas, memoria):
    y = np.array(lecturas, dtype=float)
    if 'hist' not in memoria:
        memoria['hist'] = []
        memoria['d'] = None
        memoria['m'] = 0
        memoria['k'] = 0
    hist = memoria['hist']
    k = memoria['k']
    if len(hist) >= DELAY:
        u_old = np.array(hist[-DELAY])
        r = y - C - B @ u_old
        d = memoria['d']
        if d is None:
            m = 1 if (r[0] < -1.2 and y[0] < -0.75) else 0
            dc = r + np.array([JUMP * m, 0.0])
            d = dc
        else:
            d = np.array(d)
            cands = []
            for m in (0, 1):
                if m == 1 and y[0] > -0.75:
                    continue
                dc = r + np.array([JUMP * m, 0.0])
                cands.append((abs(dc[0] - d[0]), m, dc))
            _, m, dc = min(cands, key=lambda t: t[0])
            d = d + ALPHA * (dc - d)
        memoria['d'] = list(d)
        memoria['m'] = m
    d = np.zeros(2) if memoria['d'] is None else np.array(memoria['d'])
    m = memoria['m']
    if m == 1:
        u = BI @ (TGT_LOW - C - d + np.array([JUMP, 0.0]))
    else:
        u = BI @ (TGT - C - d)
    u = np.clip(u, -3, 3)
    hist.append([float(u[0]), float(u[1])])
    if len(hist) > 10:
        del hist[0]
    memoria['k'] = k + 1
    return [float(u[0]), float(u[1])]
