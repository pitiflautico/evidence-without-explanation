import numpy as np
M=np.array([[-0.89,-1.34],[-0.8,0.85]]); Mi=np.linalg.inv(M)
def controlar(lecturas, memoria):
    u=memoria.get('u',np.array([0.44,0.86]))
    y=np.array(lecturas,dtype=float)
    e=np.array([-0.8,0.71])-y
    if abs(y[0])>0.9: e[0]=0.3*np.sign(e[0])
    u=np.clip(u+0.2*Mi@e,-3,3)
    memoria['u']=u
    return [float(u[0]),float(u[1])]
