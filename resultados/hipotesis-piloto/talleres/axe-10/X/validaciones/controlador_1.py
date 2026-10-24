import numpy as np
G=np.array([[1.27,-0.55],[-1.0,-1.2]]);Gi=np.linalg.inv(G)
T=np.array([-0.39,0.54])
def controlar(l,m):
    u=m.get('u',np.array([-1.32,0.65]))
    e=T-np.array(l)
    u=np.clip(u+0.2*Gi@e,-3,3)
    m['u']=u
    return [float(u[0]),float(u[1])]