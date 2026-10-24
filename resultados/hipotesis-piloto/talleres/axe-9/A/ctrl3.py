import numpy as np
T=np.array([-0.13,-1.31])
H=6
def controlar(lecturas,memoria):
    t=memoria.get('t',0); memoria['t']=t+1
    u=memoria.get('u',np.zeros(2))
    if 'B' not in memoria: memoria['B']=np.array([[0.6,-0.6],[-0.43,-0.8]])
    B=memoria['B']
    if t>0 and t%H==0:
        y=np.array(lecturas)
        e1=abs(y[0]-T[0]); pe=memoria.get('pe')
        if pe is not None and e1>pe+0.15 and e1>0.4:
            B[0]=-B[0]; memoria['c']=None
        memoria['pe']=e1
        c=memoria.get('c'); cn=y-B@u
        if c is None: c=cn.copy(); memoria['k2']=False
        c[0]=cn[0]
        if -1.0<y[1]<1.0: c[1]=cn[1]; memoria['k2']=True
        elif not memoria.get('k2'):
            c[1]=cn[1]+(0.5 if y[1]>0 else -0.5)
        memoria['c']=c
        u=np.clip(np.linalg.solve(B,T-c),-3,3)
    memoria['u']=u
    return [float(u[0]),float(u[1])]
