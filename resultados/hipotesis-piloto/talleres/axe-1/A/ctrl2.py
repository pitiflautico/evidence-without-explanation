
import numpy as np
T=np.array([1.09,0.51])
def controlar(lecturas, memoria):
    m=memoria
    t=m.get('t',0);m['t']=t+1
    y=np.array(lecturas,float)
    H=m.setdefault('H',[]); H.append(y)
    U=m.setdefault('U',[])
    if t<2: a=[0.0,0.0]
    elif t<6: a=[1.0,0.0]
    else:
        if t==6:
            b=(H[2][0]+H[3][0])/2; g=(H[4][0]+H[5][0])/2-b
            g=g if abs(g)>0.3 else 1.0
            m['J']=np.array([[g,-1.16],[0.78*np.sign(g),1.05]])
            m['u']=np.array([0.0,0.0])
        J=m['J']
        # RLS-ish update rows from last step increments
        if t>=9:
            du=np.array([U[-2][0]-U[-3][0], U[-1][1]-U[-2][1]])
            dy=H[-1]-H[-2]
            if np.linalg.norm(du)>0.05:
                for i in range(2):
                    if i==1 and (abs(H[-1][1])>1.12 or abs(H[-2][1])>1.12): continue
                    err=dy[i]-J[i]@du
                    J[i]+=0.5*err*du/(du@du+0.1)
        if y[1]<-1.0 and m.get('n',0)<3 and t<35:
            m['n']=m.get('n',0)+1
        e=T-y
        try: Ji=np.linalg.inv(J)
        except Exception: Ji=np.eye(2)
        if abs(np.linalg.det(J))<0.2: Ji=np.linalg.pinv(J)
        if abs(y[1])<1.12: du=0.35*Ji@e
        else: du=np.array([0.0,0.35*e[0]/J[0,1]])+np.array([0.15*np.sign(J[1,0])*np.sign(e[1]),0.15*np.sign(e[1])])
        du=np.clip(du,-0.6,0.6)
        m['u']=np.clip(m['u']+du,-3,3)
        a=[float(x) for x in m['u']]
    U.append(a)
    return a
