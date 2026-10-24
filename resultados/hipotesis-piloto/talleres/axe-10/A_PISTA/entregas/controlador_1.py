def controlar(lecturas, memoria):
    u=memoria.get('u',[0.0,0.0])
    y1,y2=lecturas
    if y1>-0.95:
        e=[-0.3-y1,0.54-y2]
    else:
        e=[4.0,0.54-y2]
    k=0.15
    u=[u[0]+k*(0.577*e[0]-0.267*e[1]), u[1]+k*(-0.477*e[0]-0.606*e[1])]
    u=[max(-3,min(3,x)) for x in u]
    memoria['u']=u
    return u