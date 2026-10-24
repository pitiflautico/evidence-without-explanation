
import numpy as np
T = np.array([-0.80, 0.71])
J = np.array([[-0.9, -1.3], [-0.8, 0.83]])
Ji = np.linalg.inv(J)
U0 = np.array([0.45, 0.85])
SAT = 0.9
def controlar(lecturas, memoria):
    y = np.array(lecturas[:2], dtype=float)
    u = np.array(memoria.get('u', U0.tolist()))
    e = T - y
    if y[0] < -SAT:
        e[0] = 0.4
    elif y[0] > SAT:
        e[0] = -1.0
    e[1] = np.clip(e[1], -1.0, 1.0)
    g = 0.25
    if abs(e[0]) < 0.1 and abs(e[1]) < 0.1:
        g = 0.12
    u = u + g * Ji.dot(e)
    u = np.clip(u, -3, 3)
    memoria['u'] = u.tolist()
    return u.tolist()
