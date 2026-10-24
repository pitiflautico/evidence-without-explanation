import numpy as np
G=np.array([[0.6,-0.75],[-1.25,-0.67]]);Gi=np.linalg.inv(G)
T=np.array([0.85,-0.37])
def controlar(l,m):
    u=m.get('u',np.array([1.275,-0.513]))
    e=T-np.array(l)
    u=np.clip(u+0.3*Gi@e,-3,3);m['u']=u
    return list(map(float,u))