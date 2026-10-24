
def controlar(l,m):
    t=m.get('t',0);m['t']=t+1
    if 'u1' not in m:
        if l[1]>-0.38:
            m['hold']=0
            return [3.0,-3.0]
        m['hold']=m.get('hold',0)+1
        if m['hold']<1: return [3.0,-3.0]
        m['u1']=2.3;m['u2']=0.0
    u1=m['u1'];u2=m['u2']
    if l[1]>-0.38:
        u2=-3.0
    else:
        u2=min(0.0,u2+0.5)
    u1+=0.25*(1.48-l[0])
    u1=max(-3,min(3,u1))
    m['u1']=u1;m['u2']=u2
    return [u1,u2]
