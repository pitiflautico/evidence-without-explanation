
import numpy as np
T = np.array([-0.98, 0.71])
J = np.array([[-0.9, -1.3], [-0.8, 0.83]])
Ji = np.linalg.inv(J)
U0 = np.array([0.447, 0.877])
def controlar(lecturas, memoria):
    y = np.array(lecturas[:2], dtype=float)
    u = np.array(memoria.get('u', U0.tolist()))
    e = T - y
    e[0] = np.clip(e[0], -1.0, 1.0)
    k = memoria.get('k', 0)
    g = 0.25
    if abs(e[0]) < 0.12 and abs(e[1]) < 0.12:
        g = 0.1
    u = u + g * Ji.dot(e)
    u = np.clip(u, -3, 3)
    memoria['u'] = u.tolist()
    memoria['k'] = k + 1
    return u.tolist()
