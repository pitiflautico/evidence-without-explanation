import numpy as np
J=np.array([[-0.8,-1.3],[0.6,-0.7]]);Ji=np.linalg.inv(J)
def controlar(l,m):
    u=m.get('u',np.array([-1.2,0.15]))
    e=np.array([0.6,0.31])-np.array(l)
    u=np.clip(u+0.1*Ji@e,-3,3);m['u']=u
    return u.tolist()