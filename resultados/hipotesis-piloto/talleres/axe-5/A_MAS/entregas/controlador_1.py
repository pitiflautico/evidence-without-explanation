def controlar(l, m):
    if 'u' not in m:
        m['u']=[-1.2,0.2]; m['k']=0
    m['k']+=1
    if m['k']>=4:
        m['k']=0
        e1=l[0]-0.6; e2=l[1]-0.42
        u1,u2=m['u']
        if l[1]<-0.3:
            d2=-0.5
        elif l[1]>0.9:
            d2=0.4
        else:
            d2=max(-0.25,min(0.2,0.4*e2/1.2))
        d1=0.45*e1/1.01-0.6*d2
        u2+=d2; u1+=d1
        m['u']=[max(-3,min(3,u1)),max(-3,min(3,u2))]
    return list(m['u'])