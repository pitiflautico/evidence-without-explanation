import numpy as np
G0=np.array([[1.27,-0.55],[-1.0,-1.2]])
T=np.array([-0.39,0.54])
def controlar(l,m):
    y=np.array(l,float)
    if 't' not in m:
        m['t']=0;m['G']=G0.copy();m['P']=np.eye(2)*2;m['U']=[np.array([-1.32,0.65])]*4;m['Y']=[y]
    t=m['t'];U=m['U'];G=m['G']
    if t>=1:
        dy=y-m['Y'][-1];du=U[-4]-U[-5] if len(U)>=5 else np.zeros(2)
        if np.linalg.norm(du)>0.05 and np.linalg.norm(dy)<10:
            P=m['P'];k=P@du/(1+du@P@du)
            G=G+np.outer(dy-G@du,k);m['P']=P-np.outer(k,du@P)+np.eye(2)*0.01;m['G']=G
    m['Y'].append(y)
    pend=U[-1]-U[-4]
    yp=y+G@pend
    try: Gi=np.linalg.inv(G)
    except: Gi=np.linalg.inv(G0)
    u=np.clip(U[-1]+0.5*Gi@(T-yp),-3,3)
    U.append(u);m['t']=t+1
    return [float(u[0]),float(u[1])]
