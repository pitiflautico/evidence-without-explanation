import numpy as np
B=np.array([[0.6,-0.6],[-0.43,-0.8]]);Bi=np.linalg.inv(B)
T=np.array([-0.13,-1.31])
H=6
def controlar(lecturas,memoria):
    t=memoria.get('t',0); memoria['t']=t+1
    u=memoria.get('u',np.zeros(2))
    if t>0 and t%H==0:
        y=np.array(lecturas); c=memoria.get('c',None)
        cn=y-B@u
        if c is None: c=cn.copy()
        if abs(y[0])<3.3: c[0]=cn[0]
        if -1.0<y[1]<1.0: c[1]=cn[1]
        elif y[1]>=1.0: c[1]=max(c[1],cn[1]) if 'c' in memoria else cn[1]
        elif y[1]<=-1.0: c[1]=min(c[1],cn[1]) if 'c' in memoria else cn[1]
        memoria['c']=c
        u=np.clip(Bi@(T-c),-3,3)
    memoria['u']=u
    return [float(u[0]),float(u[1])]
