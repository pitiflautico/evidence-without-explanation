def controlar(l, m):
    T = [-0.35, -1.35]
    if 'g' not in m:
        m.update(g=[1, 1], i=[0.0, 0.0], h=[[], []], c=[0, 0])
    out = []
    for k in range(2):
        e = T[k] - l[k]
        h = m['h'][k]; h.append(abs(e))
        if len(h) > 8: h.pop(0)
        # error growing steadily and large -> flip sign
        if len(h) == 8 and h[-1] > 0.6 and all(h[j+1] > h[j] - 0.02 for j in range(7)) and h[-1] - h[0] > 0.5:
            m['g'][k] *= -1; m['i'][k] = 0.0; m['h'][k] = []
        g = m['g'][k]
        if k == 0:
            m['i'][0] = max(-3, min(3, m['i'][0] + 0.3*e*g)); u = m['i'][0] + 0.3*e*g
        else:
            m['i'][1] = max(-3, min(3, m['i'][1] + 0.25*e*g)); u = m['i'][1] + 1.2*e*g
        out.append(max(-3, min(3, u)))
    return out