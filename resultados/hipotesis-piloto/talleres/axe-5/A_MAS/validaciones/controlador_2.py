def controlar(l, m):
    if 'u' not in m:
        m['u']=[-1.2,0.2]; m['prev']=None; m['k']=0
    m['k']+=1
    p=m['prev']; m['prev']=list(l)
    nuevo = p is None or abs(l[0]-p[0])>0.04 or abs(l[1]-p[1])>0.04 or m['k']>=4
    if nuevo and m['k']>=2:
        m['k']=0
        e1=l[0]-0.6; e2=l[1]-0.31
        u1,u2=m['u']
        d2=max(-0.15,min(0.15,0.5*e2/1.2))
        d1=0.7*e1/1.01
        u2+=d2; u1+=d1-1.24*d2
        m['u']=[max(-3,min(3,u1)),max(-3,min(3,u2))]
    return list(m['u'])