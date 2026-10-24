def controlar(l, m):
    e0=-0.13-l[0]; e1=-1.31-l[1]
    u0=0.833*e0; u1=0.533*e0-0.8*e1
    k=0.7
    c=lambda x:max(-3,min(3,k*x))
    return [c(u0),c(u1)]