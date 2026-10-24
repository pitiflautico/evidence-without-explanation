
def controlar(l, m):
    e1=0.33-l[0]; e2=0.7-l[1]
    i1=m.get('i1',0)+e1; i2=m.get('i2',0)+e2
    i1=max(-20,min(20,i1)); i2=max(-20,min(20,i2))
    m['i1']=i1; m['i2']=i2
    u2=-(3*e1+0.3*i1)
    u2=max(-3,min(3,u2))
    u1=(3*e2+0.3*i2+0.15*u2/0.1*0.1*10*0.1)
    u1=(0.3*e2+0.03*i2+0.15*u2)/0.1
    u1=max(-3,min(3,u1))
    return [u1,u2]
