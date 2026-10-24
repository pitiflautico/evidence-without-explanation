
import numpy as np
R=np.array([-0.35,-1.35])
def controlar(l,m):
    y=np.array(l,float)
    if 'th' not in m:
        m['th']=[np.array([0.85,0.1,0.07,-0.05]),np.array([0.91,-0.075,0.124,0.04])]
        m['P']=[np.eye(4)*0.5 for _ in range(2)]
        m['t']=0
    th=m['th'];P=m['P']
    if 'up' in m:
        for i in range(2):
            x=np.array([m['yp'][i],m['up'][0],m['up'][1],1.0])
            Pi=P[i];k=Pi@x/(0.97+x@Pi@x)
            th[i]=th[i]+k*(y[i]-x@th[i]);P[i]=np.clip((Pi-np.outer(k,x@Pi))/0.97,-50,50)
    B=np.array([[th[0][1],th[0][2]],[th[1][1],th[1][2]]])
    want=y+0.5*(R-y)
    rhs=np.array([want[i]-th[i][0]*y[i]-th[i][3] for i in range(2)])
    u=np.linalg.solve(B.T@B+0.01*np.eye(2),B.T@rhs)
    m['t']+=1
    if m['t']<12: u=u+np.random.uniform(-0.8,0.8,2)
    u=np.clip(u,-3,3)
    m['up']=u.copy();m['yp']=y.copy()
    return [float(u[0]),float(u[1])]
