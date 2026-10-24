
T=[1.09,0.51]
def controlar(lecturas, memoria):
    u=memoria.get('u',[-1.0,0.22])
    e0=T[0]-lecturas[0]; e1=T[1]-lecturas[1]
    k=memoria.get('k',0.35)
    # J=[[-1.15,-1],[a,-b]] a=b=1 ; inv = 1/2.15*[[-1,1],[-1,-1.15]]
    d0=(-e0+e1)/2.15; d1=(-e0-1.15*e1)/2.15
    u=[u[0]+k*d0, u[1]+k*d1]
    u=[max(-3,min(3,x)) for x in u]
    memoria['u']=u
    return list(u)
