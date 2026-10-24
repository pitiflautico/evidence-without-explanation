import numpy as np
T=np.array([-0.13,-1.31])
def controlar(l, m):
    l=np.array(l,float)
    u=m.get('u',np.array([0.0,2.0]))
    prev=m.get('prev')
    if prev is None or np.abs(l-prev).max()>0.02:
        e=T-l
        u=u+np.array([-1.0*e[0], -1.0*e[1]])
        u=np.clip(u,-3,3)
    m['prev']=l;m['u']=u
    return list(u)