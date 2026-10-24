import numpy as np
B=np.array([[0.6,-0.8],[-1.2,-0.66]]);Bi=np.linalg.inv(B)
T=np.array([0.85,-0.37])
def controlar(l,m):
    u=m.get('u',np.array([1.285,-0.473]))
    e=T-np.array(l)
    u=np.clip(u+0.3*Bi@e,-3,3)
    m['u']=u
    return list(map(float,u))