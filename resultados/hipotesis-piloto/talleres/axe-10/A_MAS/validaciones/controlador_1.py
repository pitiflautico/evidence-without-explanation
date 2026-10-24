import numpy as np
Bi=np.linalg.inv(np.array([[1.24,-0.53],[-1.0,-1.22]]))
t=np.array([-0.39,0.54])
def controlar(lecturas, memoria):
    b=memoria.get('b',np.array([1.65,-0.02]))
    e=t-np.array(lecturas)
    b=b-0.2*e
    memoria['b']=b
    u=np.clip(Bi@(t-b),-3,3)
    return list(map(float,u))