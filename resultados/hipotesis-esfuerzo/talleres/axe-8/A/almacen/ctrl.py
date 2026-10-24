
import numpy as np
A0,B00,B01,C0,L0=0.83,0.154,0.119,-0.047,1.06
A1,B10,B11,C1=0.9095,-0.0737,0.1248,0.0463
T=np.array([-0.35,-1.35])
LAM=0.55
def _F(): 
    F=np.eye(5); F[0,0]=A0; F[1,1]=A1; F[0,3]=1; F[1,4]=1; return F
def _init(r):
    f=[]
    for p in range(3):
        s=np.array([r[0],r[1],r[0],0.,0.])
        P=np.diag([0.3,0.01,0.002,0.02,0.02])
        f.append({'s':s,'P':P,'J':0.0,'p':p})
    return f
def _step(fl,u,t1,r):
    F=_F(); s=fl['s']; P=fl['P']
    s=F@s+np.array([B00*u[0]+B01*u[1]+C0, B10*u[0]+B11*u[1]+C1,0,0,0]) 
    s[2]=fl['s'][2]
    P=F@P@F.T
    if t1%3==fl['p']:
        G=np.eye(5); G[2,:]=0; G[2,0]=1
        s[2]=s[0]; P=G@P@G.T
    Q=np.diag([4e-4,4e-4,1e-6,3e-4,3e-4]); P=P+Q
    # measurements
    H=[];z=[];R=[]
    H.append([0,1,0,0,0]); z.append(r[1]); R.append(8e-4)
    if abs(r[0])<L0-0.08:
        H.append([0,0,1,0,0]); z.append(r[0]); R.append(5e-4)
    H=np.array(H,float); z=np.array(z); R=np.diag(R)
    S=H@P@H.T+R; K=P@H.T@np.linalg.inv(S); v=z-H@s
    s=s+K@v; P=(np.eye(5)-K@H)@P
    if len(z)>1:
        fl['J']=0.9*fl['J']+v[1]**2/S[1,1]
    fl['s']=s; fl['P']=P
def controlar(lecturas, memoria):
    r=np.array(lecturas,float)
    if 'f' not in memoria:
        memoria['f']=_init(r); memoria['t']=0; memoria['u']=None
    else:
        t1=memoria['t']+1; memoria['t']=t1
        for fl in memoria['f']: _step(fl,memoria['u'],t1,r)
    fl=min(memoria['f'],key=lambda f:f['J'])
    s=fl['s']; d0,d1=s[3],s[4]
    B=np.array([[B00,B01],[B10,B11]])
    A=np.diag([A0,A1])
    xs=np.array([T[0],T[1]])
    uss=np.linalg.solve(B,(np.eye(2)-A)@xs-np.array([C0+d0,C1+d1]))
    e=np.array([s[0],s[1]])-xs
    u=uss+np.linalg.solve(B,(LAM*np.eye(2)-A)@e)
    u=np.clip(u,-3,3)
    memoria['u']=u
    return [float(u[0]),float(u[1])]
