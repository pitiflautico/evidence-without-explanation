import numpy as np
def controlar(l, m):
    y1,y2=l; t1,t2=-0.35,-1.35
    if 'p' in m:
        d=y2-m['p']
        m['d']=0.7*m.get('d',0.0)+0.3*d
    e1=y1-t1
    if abs(y1)>1.0: e1*=1.5
    if abs(y2-t2)<0.5:
        m['i']=float(np.clip(m.get('i',0.0)+e1,-30,30))
    u1=float(np.clip(-0.6*e1-0.07*m.get('i',0.0),-3,3))
    want=-0.35*(y2-t2)
    base=0.02*y1-0.084*y2-0.093*u1+0.056
    u2=(want-base-m.get('d',0.0))/0.123
    u2=float(np.clip(u2,-3,3))
    m['p']=y2+base+0.123*u2+m.get('d',0.0)
    return [u1,u2]
