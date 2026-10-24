def controlar(lecturas, memoria):
    u2 = memoria.get('u2', 2.3)
    e = 0.71 - lecturas[1]
    u2 = max(-3, min(3, u2 + 0.15*e))
    memoria['u2'] = u2
    return [2.0, u2]
