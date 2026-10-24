
def controlar(l, m):
    T = [-0.35, -1.35]
    if 'g' not in m:
        m.update(g=[1, 1], i=[0.7, -0.9], c=[0, 0], t=0)
    m['t'] += 1
    e = [T[0]-l[0], T[1]-l[1]]
    u = [0, 0]
    for k in range(2):
        g = m['g'][k]
        ki, kp = (0.12, 0.5) if k == 0 else (0.25, 1.5)
        m['i'][k] = max(-3, min(3, m['i'][k] + ki*e[k]*g))
        u[k] = max(-3, min(3, m['i'][k] + kp*e[k]*g))
        # sign-flip detector: big error, actuator saturated toward correction, not improving
        if abs(e[k]) > (0.9 if k == 0 else 1.2) and abs(u[k]) >= 2.9:
            m['c'][k] += 1
        else:
            m['c'][k] = 0
        if m['c'][k] >= 10:
            m['g'][k] *= -1; m['i'][k] = 0.0; m['c'][k] = 0
    # decouple u1 effect on y2
    u[1] = max(-3, min(3, u[1] + 0.6*(u[0]-0.7)*m['g'][1]*m['g'][0]))
    return u
