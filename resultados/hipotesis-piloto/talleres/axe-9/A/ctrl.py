import numpy as np
B=np.array([[-0.6,-0.62],[0.45,-0.78]]);Bi=np.linalg.inv(B)
T=np.array([-0.13,-1.31])
def controlar(lecturas,memoria):
    u=memoria.get('u',np.zeros(2))
    e=T-np.array(lecturas)
    u=np.clip(u+0.35*Bi@e,-3,3)
    memoria['u']=u
    return [float(u[0]),float(u[1])]
