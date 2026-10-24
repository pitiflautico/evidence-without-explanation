
def controlar(l,m):
    u=m.get('u',[0.0,0.0])
    e1=-0.35-l[0]; e2=-1.35-l[1]
    u[0]=max(-3,min(3,u[0]+0.25*e1))
    p2=0.6*e2+0.5*u[0]
    u[1]=max(-3,min(3,u[1]+0.1*e2))
    m['u']=u
    return [u[0],max(-3,min(3,u[1]+p2))]
