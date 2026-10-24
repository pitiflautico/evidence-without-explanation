def controlar(lecturas, memoria):
    u=memoria.get('u',[0.0,0.0])
    e=[-0.39-lecturas[0],0.54-lecturas[1]]
    k=0.3
    u=[u[0]+k*(0.577*e[0]-0.267*e[1]), u[1]+k*(-0.477*e[0]-0.606*e[1])]
    u=[max(-3,min(3,x)) for x in u]
    memoria['u']=u
    return u