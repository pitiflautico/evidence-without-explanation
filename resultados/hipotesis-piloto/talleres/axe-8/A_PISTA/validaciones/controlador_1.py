def controlar(l, m):
    e1 = -0.35 - l[0]; e2 = -1.35 - l[1]
    m['i1'] = max(-3, min(3, m.get('i1', 0) + 0.3*e1))
    u1 = m['i1'] + 0.3*e1
    u2 = 2.0*e2
    return [max(-3, min(3, u1)), max(-3, min(3, u2))]