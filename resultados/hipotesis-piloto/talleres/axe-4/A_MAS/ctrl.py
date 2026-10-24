
import numpy as np
def controlar(l,m):
    G=np.array([[-0.034/0.17,-0.076/0.17],[0.091/0.35,-0.269/0.35]])
    Gi=np.linalg.inv(G)
    e=np.array([0.33,0.7])-np.array(l)
    I=m.get('I',np.array([-0.75,-0.3]))
    I=I+0.3*(Gi@e)
    I=np.clip(I,-3,3);m['I']=I
    u=I+0.3*(Gi@e)
    return list(np.clip(u,-3,3))
