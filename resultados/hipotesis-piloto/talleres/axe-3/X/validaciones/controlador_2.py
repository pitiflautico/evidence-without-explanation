def controlar(l, m):
    u1=m.get('u1',1.7)
    u2=-1.5 if l[1]>0 else -0.3
    u1+=0.06*(1.48-l[0])
    u1=max(-3,min(3,u1))
    m['u1']=u1
    return [u1,u2]