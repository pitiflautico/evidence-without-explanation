def controlar(l,m):
    T=[-1.06,0.44]
    u=m.setdefault('u',[0.0,0.0])
    e1=(T[0]-l[0])*0.2; e2=(T[1]-l[1])*0.5
    d=[1.325*e1+1.205*e2, -1.205*e1+0.723*e2]
    u=[max(-3,min(3,u[k]+d[k])) for k in range(2)]
    m['u']=u
    return u
