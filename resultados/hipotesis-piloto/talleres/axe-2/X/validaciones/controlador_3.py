def controlar(l,m):
    T=[-1.06,0.44]
    u=m.setdefault('u',[0.0,0.0])
    n=m.get('n',0)+1
    nuevo = ('y1' not in m) or abs(l[0]-m['y1'])>0.02 or n>=4
    e1=(T[0]-l[0])*0.4 if nuevo else 0.0
    if nuevo: n=0
    m['n']=n; m['y1']=l[0]
    e2=(T[1]-l[1])*0.5
    d=[1.325*e1+1.205*e2, -1.205*e1+0.723*e2]
    u=[max(-3,min(3,u[k]+d[k])) for k in range(2)]
    m['u']=u
    return u
