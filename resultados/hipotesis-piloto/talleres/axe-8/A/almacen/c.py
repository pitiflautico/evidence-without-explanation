import numpy as np
def controlar(l, m):
    y1,y2=l; t1,t2=-0.35,-1.35
    e1=y1-t1
    if abs(y1)>1.0: e1*=1.5
    m['i']=float(np.clip(m.get('i',0.0)+e1,-40,40))
    u1=float(np.clip(-0.6*e1-0.07*m['i'],-3,3))
    want=-0.35*(y2-t2)
    u2=(want-(0.02*y1-0.084*y2-0.093*u1+0.056))/0.123
    return [u1,float(np.clip(u2,-3,3))]
