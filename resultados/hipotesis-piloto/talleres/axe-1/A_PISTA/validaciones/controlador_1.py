def controlar(l, m):
    u1=m.get('u1',-1.1); u2=m.get('u2',0.45)
    e1=l[0]-1.09; e2=l[1]-0.51
    if m.get('t',0)>0:
        u1+=0.12*e2
        u2+=0.5*e1
    u1=max(-3,min(3,u1)); u2=max(-3,min(3,u2))
    m['u1']=u1; m['u2']=u2; m['t']=m.get('t',0)+1
    return [u1,u2]