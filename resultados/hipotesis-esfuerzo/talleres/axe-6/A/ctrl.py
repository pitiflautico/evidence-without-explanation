
import numpy as np
_A = np.array([[0.62, -0.7], [1.0, 0.55]])
_T = (0.85, -0.37)
def controlar(lecturas, memoria):
    y0, y1 = float(lecturas[0]), float(lecturas[1])
    if 'v0' not in memoria:
        memoria['v0'] = 1.23; memoria['z'] = 1.0; memoria['skip'] = False
    v0 = memoria['v0']; z = memoria['z']
    v0 += 0.3 * (_T[0] - y0)
    v0 = max(-3.0, min(3.5, v0))
    reset = False
    if memoria['skip']:
        memoria['skip'] = False
    elif y1 < -0.8:
        reset = True
        memoria['skip'] = True
        z = min(z, 1.2) - 0.2
    else:
        dz = -0.5 * (_T[1] - y1)
        z += max(-0.25, min(0.25, dz))
    z = max(-1.5, min(1.45, z))
    memoria['v0'] = v0; memoria['z'] = z
    zz = 0.0 if reset else z
    u = np.linalg.solve(_A, [v0, zz])
    u = np.clip(u, -3, 3)
    return [float(u[0]), float(u[1])]
