def controlar(l, m):
    i = m.get('i', 0.0)
    e = 1.48 - l[0]
    i += 0.15 * e
    i = max(-1.5, min(1.5, i))
    m['i'] = i
    u2 = -0.3 if l[1] > -0.6 else 0.0
    u1 = 2.3 + i + (0.43 if u2 < 0 else 0)
    return [max(-3, min(3, u1)), u2]