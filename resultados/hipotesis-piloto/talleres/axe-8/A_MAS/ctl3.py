
def controlar(l,m):
    if 'u' not in m: m.update(u=[0.0,0.0],s=[1,1],c=[0,0],pe=[None,None],hold=[0,0])
    u=m['u'];s=m['s']
    e=[-0.35-l[0],-1.35-l[1]]
    for i in range(2):
        pe=m['pe'][i]
        if m['hold'][i]>0: m['hold'][i]-=1
        elif pe is not None and abs(e[i])>0.8 and abs(e[i])>abs(pe)+0.02: m['c'][i]+=1
        else: m['c'][i]=max(0,m['c'][i]-1) if pe is not None and abs(e[i])<abs(pe) else m['c'][i]
        if m['c'][i]>=5:
            s[i]=-s[i];m['c'][i]=0;u[i]=0.0;m['hold'][i]=8
        m['pe'][i]=e[i]
    u[0]=max(-3,min(3,u[0]+0.25*s[0]*e[0]))
    u[1]=max(-3,min(3,u[1]+0.1*s[1]*e[1]))
    p2=s[1]*0.6*e[1]+0.5*u[0]*s[1]
    return [u[0],max(-3,min(3,u[1]+p2))]
