def controlar(l, m):
    u1=m.get('u1',-1.1); u2=m.get('u2',0.45)
    e1=l[0]-1.09; e2=l[1]-0.51
    h=m.get('h',[0,0])
    if m.get('t',0)>0:
        if abs(l[1])>1.1:
            d=-0.3*(1 if e2>0 else -1)
        else:
            d=-0.15*e2
        u1n=max(-3,min(3,u1+d)); d=u1n-u1; u1=u1n
        u2+=0.6*e1 - 1.15*h[0]
        h=[h[1],d]
    u2=max(-3,min(3,u2))
    m['h']=h; m['u1']=u1; m['u2']=u2; m['t']=m.get('t',0)+1
    return [u1,u2]