import numpy as np
T=np.array([0.6,0.31])
def controlar(l,m):
    l=np.array(l,float)
    if 'u' not in m:
        m.update(u=np.array([-1.2,0.15]),prev=l,k=0,ph=None,J=np.array([[-0.8,-1.3],[0.6,-0.7]]),ly=None,lu=None)
    k=m['k'];m['k']+=1
    if m['ph'] is None and np.max(np.abs(l-m['prev']))>0.25: m['ph']=k%4
    m['prev']=l
    if m['ph'] is not None and k%4==(m['ph']+1)%4:
        if m['ly'] is not None:
            du=m['u']-m['lu'];dy=l-m['ly']
            n=du@du
            if n>1e-3:
                m['J']=m['J']+np.outer(dy-m['J']@du,du)/n*0.8
        e=T-l
        J=m['J']
        if abs(np.linalg.det(J))<0.1: J=J+0.3*np.eye(2)*-1
        try: step=np.linalg.solve(J,e)*0.6
        except Exception: step=np.zeros(2)
        nn=np.linalg.norm(step)
        if nn>0.8: step*=0.8/nn
        m['ly']=l.copy();m['lu']=m['u'].copy()
        m['u']=np.clip(m['u']+step,-3,3)
    return m['u'].tolist()
