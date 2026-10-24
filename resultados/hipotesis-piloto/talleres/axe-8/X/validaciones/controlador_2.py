def controlar(l, m):
    e1=l[0]+0.35; e2=l[1]+1.35
    m['I1']=m.get('I1',0)+e1; m['I2']=m.get('I2',0)+e2
    c=lambda v:max(-3,min(3,v))
    m['I1']=max(-8,min(8,m['I1'])); m['I2']=max(-15,min(15,m['I2']))
    u1=c(-(0.8*e1+0.25*m['I1']))
    u2=c(-1.5*e2-0.1*m['I2']+1.2*u1)
    return [u1,u2]