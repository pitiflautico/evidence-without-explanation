def controlar(l, m):
    t=[-0.98,0.71]
    u=m.get('u',[0.0,0.0])
    for i in range(2):
        u[i]=max(-3,min(3,u[i]+0.3*(t[i]-l[i])))
    m['u']=u
    return list(u)