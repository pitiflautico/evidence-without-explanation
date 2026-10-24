def controlar(l, m):
    e1=0.33-l[0]; e2=0.7-l[1]
    m['i1']=max(-2,min(2,m.get('i1',0)+0.3*e1))
    m['i2']=max(-2,min(2,m.get('i2',0)+0.15*e2))
    c=lambda x:max(-3,min(3,x))
    d=c(1.0*e2+m['i2']); s=c(-3*e1-m['i1'])
    return [c((s+d)/2),c((s-d)/2)]