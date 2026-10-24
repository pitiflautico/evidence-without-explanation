def controlar(l,m):
    u=m.get('u',[0.0,0.0])
    e1=-1.06-l[0]; e2=0.44-l[1]
    u1=min(3,max(-3,u[0]+0.3*e2))
    u2=min(1.0,max(-3,u[1]-0.08*e1))
    m['u']=[u1,u2]
    return [u1,u2]
