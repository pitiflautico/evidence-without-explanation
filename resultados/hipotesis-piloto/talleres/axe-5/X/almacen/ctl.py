
import numpy as np
def controlar(l,m):
    y1,y2=l
    if 'u2' not in m: m['u2']=-0.3; m['i1']=0.0
    e2=y2-0.31; e1=y1-0.6
    m['u2']=float(np.clip(m['u2']-0.06*e2,-3,3))
    u2=m['u2']
    m['i1']=float(np.clip(m['i1']+0.08*e1,-2,2))
    u1=-(0.96+1.25*u2)/1.02+m['i1']
    return [float(np.clip(u1,-3,3)),u2]
