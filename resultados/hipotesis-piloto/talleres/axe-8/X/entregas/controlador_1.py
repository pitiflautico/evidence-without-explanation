def controlar(l, m):
    e1=l[0]+0.35; e2=l[1]+1.35
    s1=m.get('s1',1); s2=m.get('s2',1)
    m['I1']=max(-8,min(8,m.get('I1',0)+e1)); m['I2']=max(-15,min(15,m.get('I2',0)+e2))
    # detect divergence: error large and growing for a while -> flip sign
    for k,e in (('1',e1),('2',e2)):
        h=m.setdefault('h'+k,[]); h.append(abs(e))
        if len(h)>=9 and h[-1]>0.6 and h[-1]>h[-9]+0.05 and all(h[i]>=h[i-1]-0.05 for i in range(len(h)-8,len(h))):
            m['s'+k]=-m.get('s'+k,1); m['I'+k]=0; m['h'+k]=[]
    s1=m.get('s1',1); s2=m.get('s2',1)
    c=lambda v:max(-3,min(3,v))
    u1=c(-s1*(0.8*e1+0.25*m['I1']))
    u2=c(s2*(-1.5*e2-0.1*m['I2'])+1.2*u1*s1*s2)
    return [u1,u2]