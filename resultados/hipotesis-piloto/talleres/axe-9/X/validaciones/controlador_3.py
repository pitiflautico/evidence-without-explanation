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
    if abs(y[1])<1.0: c1=y[1]-p[1]
    elif y[1]>0: c1=max(c1 if c1 is not None and m.get('ok') else -9,1.1-p[1])+0.4
    else:
        lb=-1.1-p[1]
        if c1 is None or c1>lb: c1=lb-0.4
    if abs(y[1])<1.0: m['ok']=True
    m['c1']=c1
    tg=np.array([-0.13,-1.25])
    un=np.clip(Bi@(tg-np.array([c0,c1])),-3,3)
    m['u']=list(un); return list(un)