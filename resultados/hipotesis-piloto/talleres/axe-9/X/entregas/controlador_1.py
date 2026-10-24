import numpy as np
B=np.array([[-0.603,-0.624],[0.433,-0.793]]);Bi=np.linalg.inv(B)
def controlar(l, m):
    t=m.get('t',0); m['t']=t+1
    u=np.array(m.get('u',[0.0,0.0]))
    if t%3!=0: return list(u)
    if t==0:
        m['u']=[0.0,0.0]; return [0.0,0.0]
    y=np.array(l); p=B@u
    c0=y[0]-p[0]
    c1=m.get('c1',None)
    if abs(y[1])<1.0:
        c1=y[1]-p[1]; m['ok']=True
    elif y[1]>0:
        lb=1.1-p[1]
        if c1 is None or c1<lb: c1=lb+0.4
    else:
        ub=-1.1-p[1]
        if c1 is None: c1=ub-0.4
        elif c1>ub: c1=ub-(0.0 if m.get('ok') else 0.3)
        c1=max(c1,ub-1.0)
    m['c1']=c1
    tg=np.array([-0.13,-1.25])
    un=Bi@(tg-np.array([c0,c1]))
    if np.abs(un).max()>3:
        best=None
        for a in np.linspace(-3,3,121):
            u1=np.clip((tg[0]-c0-B[0,0]*a)/B[0,1],-3,3)
            v=np.array([a,u1]); r=B@v+np.array([c0,c1])-tg
            s=10*r[0]**2+r[1]**2
            if best is None or s<best[0]: best=(s,v)
        un=best[1]
    un=np.clip(un,-3,3)
    m['u']=[float(x) for x in un]; return list(m['u'])