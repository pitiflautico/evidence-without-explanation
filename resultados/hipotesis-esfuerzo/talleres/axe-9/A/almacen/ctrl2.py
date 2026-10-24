
import numpy as np
J = np.array([[-0.6,-0.62],[0.43,-0.8]])
Ji = np.linalg.inv(J)
T = np.array([-0.13,-1.31])
K = 0.35
def controlar(lecturas, memoria):
    y = np.array(lecturas, dtype=float)
    u = memoria.get('u')
    u = np.array([0.3,2.5]) if u is None else np.array(u)
    e = T - y
    un = u + K*Ji.dot(e)
    if abs(un[1]) > 3.0:
        un[1] = np.clip(un[1], -3, 3)
        un[0] = u[0] + K*e[0]/J[0,0]
    elif abs(un[0]) > 3.0:
        un[0] = np.clip(un[0], -3, 3)
        un[1] = u[1] + K*e[1]/J[1,1]
    un = np.clip(un, -3, 3)
    memoria['u'] = un.tolist()
    return un.tolist()
