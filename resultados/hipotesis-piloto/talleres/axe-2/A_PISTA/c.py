import numpy as np
Gi=np.linalg.inv(np.array([[1.057,-0.9],[1.24,0.67]]))
U0=np.array([np.float64(0.6096712267292564), np.float64(1.1315805407253599)])
def controlar(l,m):
    if 'i' not in m: m['i']=np.zeros(2)
    e=np.array([-1.06,0.44])-np.array(l)
    m['i']=np.clip(m['i']+0.12*(Gi@e),-4,4)
    u=np.clip(U0+m['i'],-3,3)
    return [float(x) for x in u]
