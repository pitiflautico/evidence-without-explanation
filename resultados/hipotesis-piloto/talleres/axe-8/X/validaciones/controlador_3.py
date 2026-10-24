def controlar(l, m):
    e1=l[0]+0.35; e2=l[1]+1.35
    m['I1']=max(-5,min(5,m.get('I1',0)+e1)); m['I2']=max(-8,min(8,m.get('I2',0)+e2))
    c=lambda v:max(-1.2,min(1.2,v))
    u1=c(-(0.8*e1+0.2*m['I1']))
    u2=c(-1.2*e2-0.08*m['I2']+1.2*u1)
    return [u1,u2]