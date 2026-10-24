import numpy as np, math
A=np.array([[0.69,1.4],[-1.16,1.31]])
Ai=np.linalg.inv(A)
def plan(c1,c2,uprev):
    best=None
    for base in (-0.82,math.pi+0.82):
        for k in range(-3,4):
            th=base+2*math.pi*k
            u=Ai@np.array([1.48-c1,th-c2])
            uc=np.clip(u,-3,3)
            cost=10*np.sum((u-uc)**2)+0.05*np.sum((uc-uprev)**2)
            if best is None or cost<best[0]: best=(cost,uc)
    return best[1]
def controlar(lecturas, memoria):
    t=memoria.get('t',0); memoria['t']=t+1
    if 'u' not in memoria:
        memoria['c1']=-0.14; memoria['c2']=0.81
        memoria['u']=plan(-0.14,0.81,np.zeros(2))
        return [float(x) for x in memoria['u']]
    if t%4==3 or (t%4==0):
        pass
    if t%4==0:
        u=memoria['u']
        y1,y2=lecturas
        memoria['c1']=0.5*memoria['c1']+0.5*(y1-A[0]@u)
        s=math.asin(max(-1,min(1,y2)))
        lin=A[1]@u
        cands=[]
        for b in (s,math.pi-s):
            for k in range(-3,4):
                cands.append(b+2*math.pi*k-lin)
        c2=min(cands,key=lambda c:abs(c-memoria['c2']))
        memoria['c2']=0.5*memoria['c2']+0.5*c2
        memoria['u']=plan(memoria['c1'],c2,u)
    return [float(x) for x in memoria['u']]
