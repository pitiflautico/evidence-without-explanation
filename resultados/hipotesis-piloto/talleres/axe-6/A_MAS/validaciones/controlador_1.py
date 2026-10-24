import numpy as np
M=np.array([[0.55,-0.75],[-1.25,-0.66]]);Mi=np.linalg.inv(M)
def controlar(l,m):
    u=m.get('u',np.array([1.3,-0.58]))
    e=np.array([0.85,-0.37])-np.array(l)
    u=np.clip(u+0.25*Mi@e,-3,3);m['u']=u
    return [float(u[0]),float(u[1])]