
import numpy as np
T=np.array([0.6,0.31])
def controlar(l,m):
    y=np.array(l,float)
    if 'P' not in m:
        m['P']=(np.eye(3)*10).tolist(); m['th']=np.zeros((3,2)).tolist()
        m['u']=[0.0,0.0]; m['prev']=None; m['k']=0; m['n']=0
    P=np.array(m['P']); th=np.array(m['th']); u=np.array(m['u'])
    m['k']+=1
    new = m['prev'] is None or np.any(np.abs(y-np.array(m['prev']))>1e-9)
    if m['prev'] is not None and new:
        x=np.r_[u,1.0]
        g=P@x/(0.9+x@P@x)
        th=th+np.outer(g,y-x@th)
        P=(P-np.outer(g,x@P))/0.9
        P=np.clip(P,-1e3,1e3)
        m['n']+=1
    m['prev']=y.tolist()
    if new:
        B=th[:2].T; c=th[2]
        if m['n']<3:
            un=np.random.uniform(-1,1,2)
        else:
            try:
                du=np.linalg.solve(B.T@B+0.05*np.eye(2),B.T@(T-y))
            except Exception:
                du=np.zeros(2)
            n=np.linalg.norm(du)
            if n>0.8: du*=0.8/n
            un=u+du+np.random.normal(0,0.08,2)
        u=np.clip(un,-3,3)
    m['P']=P.tolist(); m['th']=th.tolist(); m['u']=u.tolist()
    return [float(u[0]),float(u[1])]
