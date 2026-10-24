def controlar(l, m):
    t=[-0.35,-1.35]
    return [max(-3,min(3,-1.2*(l[i]-t[i]))) for i in range(2)]