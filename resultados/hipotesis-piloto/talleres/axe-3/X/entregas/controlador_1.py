def controlar(l, m):
    u=m.get('u',[1.7,0.3])
    e1=1.48-l[0]; e2=-0.73-l[1]
    if l[1]>0.9:
        u[1]-=0.4
        u[0]+=0.05*e1
    elif l[1]<-0.97:
        u[1]+=0.05
        u[0]-=0.05
        u[0]+=0.03*e1; u[1]+=0.03*e1
    else:
        g=0.15/1.96
        u[0]+=g*(1.25*e1-1.1*e2)
        u[1]+=g*(1.1*e1+0.6*e2)
    u=[max(-3,min(3,x)) for x in u]
    m['u']=u
    return list(u)