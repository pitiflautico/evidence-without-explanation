
def controlar(l, m):
    t=m.get("t",0); m["t"]=t+1
    if t==0: m["y0"]=l[0]
    if t<4:
        return [1.0,0.0]
    if t==4:
        g=l[0]-m["y0"]
        m["s"]=1.0 if g<0 else -1.0
        m["u1"]=1.0; m["u2"]=0.0
    u1=m["u1"]; u2=m["u2"]
    e1=l[0]-1.09; e2=l[1]-0.51
    u2+=0.08*e2
    u1+=m["s"]*0.25*e1
    u1=max(-3,min(3,u1)); u2=max(-3,min(3,u2))
    m["u1"]=u1; m["u2"]=u2
    return [u1,u2]
