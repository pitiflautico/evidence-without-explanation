
def controlar(lecturas, memoria):
    t=memoria.get("t",0); memoria["t"]=t+1
    y1,y2=lecturas
    m=memoria
    if t==0:
        m.update(reset=0,u2=0.15,c=0.0,nres=0)
    samp = (t%4==3)
    s=t-m["reset"]
    if samp:
        if s>=11:
            m["c"]+=0.7*(y1-0.6)
            m["c"]=max(-5,min(5,m["c"]))
        if s>=11:
            e2=y2-0.31
            if e2>0.1: m["u2"]=min(1.2,m["u2"]+min(0.06,0.1*e2))
            elif y2<-0.1 and t<46 and m["nres"]<4:
                m["reset"]=t; m["nres"]+=1; m["u2"]=max(-0.8,m["u2"]-0.12)
    s=t-m["reset"]
    u2=-3.0 if s<8 else m["u2"]
    u1=-0.95-1.25*u2+m["c"]
    if s<8: u1=-0.95-1.25*m["u2"]+m["c"]
    u1=max(-3,min(3,u1))
    return [u1,u2]
