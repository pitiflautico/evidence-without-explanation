def controlar(l, m):
    if 'u' not in m: m['u']=[-1.2,0.2]
    e1=l[0]-0.6; e2=l[1]-0.31
    u1,u2=m['u']
    d2=0.08*e2/1.2
    d1=0.08*e1/1.01
    u2+=d2; u1+=d1-1.24*d2
    u1=max(-3,min(3,u1)); u2=max(-3,min(3,u2))
    m['u']=[u1,u2]
    return [u1,u2]