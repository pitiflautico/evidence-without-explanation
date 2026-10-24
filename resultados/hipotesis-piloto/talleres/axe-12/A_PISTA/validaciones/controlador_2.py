def controlar(l, m):
    Ai=[[-0.4676,-0.7316],[-0.4566,0.4621]]
    e=[-0.82-l[0], 0.71-l[1]]
    u=m.get('u',[0.39,0.82])
    k=0.35
    u=[u[i]+k*(Ai[i][0]*e[0]+Ai[i][1]*e[1]) for i in range(2)]
    u=[max(-3,min(3,x)) for x in u]
    m['u']=u
    return list(u)