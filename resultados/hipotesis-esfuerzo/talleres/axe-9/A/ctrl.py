
import numpy as np
J = np.array([[-0.6,-0.62],[0.43,-0.8]])
Ji = np.linalg.inv(J)
T = np.array([-0.13,-1.31])
def controlar(lecturas, memoria):
    y = np.array(lecturas, dtype=float)
    u = memoria.get('u')
    if u is None:
        u = np.array([0.7,2.6])
    else:
        u = np.array(u)
    e = T - y
    k = 0.35
    u = np.clip(u + k*Ji.dot(e), -3, 3)
    memoria['u'] = u.tolist()
    return u.tolist()
