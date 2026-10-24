
PROBE=[(0,0),(0,1),(0,-1),(0,0),(1,0),(1,0),(1,0),(0,0),(0,0)]
def controlar(l, m):
    t=m.get("t",0); m["t"]=t+1
    h=m.setdefault("h",[])
    h.append(list(l))
    if t<len(PROBE):
        a=list(PROBE[t]); m["u"]=[0.0,0.0]; return a
    if "G" not in m:
        # h[i] is reading after action i-1 (h[0] initial)
        y0=h[1]; yp=h[2]; ym=h[3]
        g12=(yp[0]-ym[0])/2; g22=(yp[1]-ym[1])/2
        if abs(yp[1])>1.1 and abs(ym[1])>1.1 and abs(g22)<0.2: g22=None
        base=h[4]; y1u=(h[7][0]+h[8][0])/2; y2u=(h[7][1]+h[8][1])/2
        g11=y1u-base[0]; g21=y2u-base[1]
        m["G"]=[g11,g12,g21,g22]
    g11,g12,g21,g22=m["G"]
    u1,u2=m["u"]
    e1=1.09-l[0]; e2=0.51-l[1]
    sat2=abs(l[1])>1.1
    e2c=max(-0.5,min(0.5,e2))
    if g22 is None or abs(g22)<0.15:
        # y2 unknown: drift u2 slowly to search
        g22=-0.6 if m.get("dir",1)>0 else 0.6
        m["cnt"]=m.get("cnt",0)+1
        if m["cnt"]>15: m["dir"]=-m.get("dir",1); m["cnt"]=0
        if not sat2: pass
    if not sat2: m["G"][3]=m["G"][3] if m["G"][3] is not None else g22
    # u2 fast loop on y2, u1 slow loop on y1 compensating u2 effect
    du2=0.35*e2c/g22
    if abs(g11)<0.2: g11=0.8 if g11>=0 else -0.8
    du1=(0.25*e1 - g12*du2)/g11
    du1=max(-0.4,min(0.4,du1)); du2=max(-0.4,min(0.4,du2))
    u1=max(-3,min(3,u1+du1)); u2=max(-3,min(3,u2+du2))
    m["u"]=[u1,u2]
    return [u1,u2]
