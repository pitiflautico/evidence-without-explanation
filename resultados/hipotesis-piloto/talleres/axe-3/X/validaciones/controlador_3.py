def controlar(l, m):
    u=m.get('u',[1.7,0.3])
    e1=1.48-l[0]; e2=-0.73-l[1]
    g=0.25/1.96
    u[0]+=g*(1.25*e1-1.1*e2)
    u[1]+=g*(1.1*e1+0.6*e2)
    u=[max(-3,min(3,x)) for x in u]
    m['u']=u
    return list(u)