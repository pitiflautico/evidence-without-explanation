import numpy as np
T=np.array([-0.13,-1.31])
def controlar(l, m):
    l=np.array(l,float)
    if 'u' not in m: m.update(u=np.array([0.0,3.0]),prev=None,s=-1.0,n=0)
    u=m['u'];prev=m['prev']
    if prev is None or np.abs(l-prev).max()>0.02 or m.get('k',0)>=3:
        m['k']=0
        e=T-l
        u=u+np.array([m['s']*0.8*e[0], -1.0*e[1]])
        if abs(u[0])>=3 and abs(e[0])>0.35:
            m['n']+=1
            if m['n']>=2:
                m['s']*=-1; u[0]=0.0; m['n']=0
        else: m['n']=0
        u=np.clip(u,-3,3)
    m['k']=m.get('k',0)+1
    m['prev']=l;m['u']=u
    return [float(u[0]),float(u[1])]
