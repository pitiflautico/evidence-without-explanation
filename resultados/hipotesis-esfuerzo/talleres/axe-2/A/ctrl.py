
A=0.829; B1=0.178; B2=-0.152; C=-0.119
K1=0.51; K2=0.58
T1=-1.06; T2=0.44
ADES=0.55

def _clip(v,lo=-3.0,hi=3.0):
    return max(lo,min(hi,v))

def controlar(lecturas, memoria):
    y1,y2=float(lecturas[0]),float(lecturas[1])
    if 'x' not in memoria:
        memoria['x']=y1; memoria['d1']=0.0; memoria['prev1']=y1; memoria['since']=0
        memoria['u']=None; memoria['o2']=None; memoria['k']=0
    m=memoria
    m['k']+=1
    u=m['u']
    if u is not None:
        # propagate model with the last applied action
        m['x']=A*m['x']+B1*u[0]+B2*u[1]+C+m['d1']
        o2=y2-(K1*u[0]+K2*u[1])
        m['o2']=o2
    # ch1 measurement handling (sample-and-hold every ~4 steps)
    m['since']+=1
    tick=False
    if abs(y1-m['prev1'])>1e-4:
        tick=True
    elif m['since']>=4:
        tick=True
    if tick and u is not None:
        e=y1-m['x']
        m['d1']+=0.12*e
        m['d1']=max(-1.0,min(1.0,m['d1']))
        m['x']=y1
        m['since']=0
    elif tick:
        m['x']=y1; m['since']=0
    m['prev1']=y1
    o2=m['o2']
    if o2 is None:
        # first step: unknown action history; assume ch2 offset from mode guess
        o2=y2  # unknown, just use reading (action history unknown)
        lowmode = y2 < -0.5
    else:
        lowmode = o2 < -0.6
    x=m['x']
    if lowmode:
        a=[2.5,2.5]
    else:
        xd=T1+ADES*(x-T1)
        r1=xd-A*x-C-m['d1']
        r2=T2-o2
        det=B1*K2-B2*K1
        a1=( r1*K2-B2*r2)/det
        a2=(B1*r2-K1*r1)/det
        # keep ch2 achievable: if clipped, prioritize ch2 safety
        if abs(a1)>3 or abs(a2)>3:
            s=3.0/max(abs(a1),abs(a2))
            # fall back: steady-state solution (no acceleration) scaled
            r1s=T1*(1-A)-C-m['d1']
            b1=( r1s*K2-B2*r2)/det; b2=(B1*r2-K1*r1s)/det
            # blend between aggressive and steady
            lo,hi=0.0,1.0
            for _ in range(20):
                mid=(lo+hi)/2
                c1=b1+mid*(a1-b1); c2=b2+mid*(a2-b2)
                if abs(c1)<=3 and abs(c2)<=3: lo=mid
                else: hi=mid
            a1=b1+lo*(a1-b1); a2=b2+lo*(a2-b2)
        a=[_clip(a1),_clip(a2)]
    m['u']=a
    return a
