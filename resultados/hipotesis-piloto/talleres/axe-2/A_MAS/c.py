
import numpy as np
def controlar(l, m):
    y1,y2=l
    if 'P' not in m:
        m['P']=np.eye(2)*1.0; m['g']=np.array([0.57,-0.91]); m['acc']=np.zeros(2); m['y1']=y1; m['s']=0.16; m['k']=0
    acc=m['acc']; d=y1-m['y1']
    if abs(d)>0.08 and np.abs(acc).sum()>0.05:
        x=acc; P=m['P']; g=m['g']
        K=P@x/(0.05+x@P@x); m['g']=g+K*(d-x@g); m['P']=(P-np.outer(K,x@P))/0.95+np.eye(2)*0.01
        m['acc']=np.zeros(2)
    elif abs(d)>0.08: m['acc']=np.zeros(2)
    m['y1']=y1
    s=m['s']+0.5*(0.44-y2)/0.55; s=max(-3,min(3,s)); m['s']=s
    g=m['g']; r=0.4*(-1.06-y1)
    den=g[0]-g[1]
    if abs(den)<0.2: den=0.2 if den>=0 else -0.2
    a=(r-g[1]*s)/den
    a=max(-3,min(3,a)); b=max(-3,min(3,s-a))
    m['acc']=m['acc']+np.array([a,b])
    return [a,b]
