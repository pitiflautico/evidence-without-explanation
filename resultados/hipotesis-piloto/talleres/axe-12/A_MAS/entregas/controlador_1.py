def controlar(l,m):
    u=m.get('u',[0.0,0.0]);g=[-0.98,0.71];s=[-1,1]
    u=[max(-3,min(3,u[i]+0.25*s[i]*(g[i]-l[i]))) for i in range(2)]
    m['u']=u;return u