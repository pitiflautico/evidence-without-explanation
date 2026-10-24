
import numpy as np
B=np.array([[0.69,0.7],[-1.18,1.37]]);Bi=np.linalg.inv(B)
T=np.array([1.48,-0.73])
def controlar(l,m):
    u=m.get('u',np.zeros(2))
    e=T-np.array(l)
    u=np.clip(u+0.15*Bi@e,-3,3)
    m['u']=u
    return [float(u[0]),float(u[1])]
