import numpy as np
J=np.array([[-0.8,-1.3],[0.6,-0.7]]);Ji=np.linalg.inv(J)
def controlar(l,m):
    l=np.array(l)
    if 'u' not in m:
        m['u']=np.array([-1.2,0.15]);m['prev']=l;m['k']=0;m['ph']=None
    k=m['k'];m['k']+=1
    if m['ph'] is None and np.max(np.abs(l-m['prev']))>0.25: m['ph']=k%4
    m['prev']=l
    upd = (m['ph'] is not None and k%4==(m['ph']+1)%4)
    if upd:
        e=np.array([0.6,0.31])-l
        m['u']=np.clip(m['u']+0.5*Ji@e,-3,3)
    return m['u'].tolist()