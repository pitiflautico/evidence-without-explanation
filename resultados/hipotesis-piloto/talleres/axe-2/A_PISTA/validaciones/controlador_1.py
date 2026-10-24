import numpy as np
J=np.array([[-0.9,-0.6],[0.53,0.55]]);Ji=np.linalg.inv(J)
def controlar(l,m):
    u=m.get('u',np.zeros(2))
    e=np.array([-1.06,0.44])-np.array(l)
    u=np.clip(u+0.4*Ji@e,-3,3);m['u']=u
    return list(map(float,u))