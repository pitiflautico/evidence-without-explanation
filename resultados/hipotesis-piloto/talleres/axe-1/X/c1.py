
def controlar(l, m):
    u1=m.get('u1',0.0); u2=m.get('u2',-0.9)
    e1=1.09-l[0]; e2=0.51-l[1]
    u1+=0.08*e2
    u2-=0.5*e1
    u1=max(-3,min(3,u1)); u2=max(-3,min(3,u2))
    m['u1']=u1; m['u2']=u2
    return [u1,u2]
