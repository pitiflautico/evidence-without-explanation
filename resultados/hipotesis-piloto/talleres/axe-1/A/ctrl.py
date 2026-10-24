
import numpy as np
J=np.array([[1.0,-1.16],[0.78,1.05]]);Ji=np.linalg.inv(J)
T=np.array([1.09,0.51])
def controlar(lecturas, memoria):
    t=memoria.get('t',0);memoria['t']=t+1
    y=np.array(lecturas,float)
    if 'u' not in memoria: memoria['u']=np.array([-0.28,-1.05]); memoria['r']=4
    r=memoria['r']
    if r>0:
        memoria['r']=r-1
        if r==1: memoria['w']=3
        return [1.0,0.0]
    w=memoria.get('w',0)
    if w>0:
        memoria['w']=w-1; return [float(x) for x in memoria['u']]
    if y[1]<-0.9 and memoria.get('n',0)<6:
        memoria['n']=memoria.get('n',0)+1; memoria['r']=4; return [1.0,0.0]
    e=T-y
    if abs(y[1])<1.15:
        du=0.3*Ji@e
    else:
        du=np.array([0.3*e[0],0.0])
    memoria['u']=np.clip(memoria['u']+du,-3,3)
    return [float(x) for x in memoria['u']]
