def controlar(l, m):
    t=[-1.06,0.44]
    u=m.get('u',[0.0,0.0])
    e=[t[0]-l[0], t[1]-l[1]]
    u[0]=max(-3,min(3,u[0]-0.3*e[0]))
    u[1]=max(-3,min(3,u[1]+0.3*e[1]))
    m['u']=u
    return list(u)