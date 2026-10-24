def controlar(l, m):
    t=[-0.35,-1.35]
    e=[l[0]-t[0], l[1]-t[1]]
    I=m.get('I',[0,0])
    I=[I[0]+e[0], I[1]-e[1]]
    m['I']=I
    u1=max(-3,min(3, 1.5*e[0]+0.5*I[0]))
    u2=max(-3,min(3, -1.5*e[1]+0.5*I[1]))
    return [u1,u2]