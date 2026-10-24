import numpy as np
M=np.array([[-0.89,-1.34],[-0.8,0.85]]); Mi=np.linalg.inv(M)
def controlar(lecturas, memoria):
    u=memoria.get('u',np.array([0.44,0.86]))
    e=np.array([-0.98,0.71])-np.array(lecturas)
    u=np.clip(u+0.2*Mi@e,-3,3)
    memoria['u']=u
    return [float(u[0]),float(u[1])]
