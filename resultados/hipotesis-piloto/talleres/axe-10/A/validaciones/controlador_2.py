Bi=[[-1.2/-2.074,0.55/-2.074],[1.0/-2.074,1.27/-2.074]]
T=[-0.39,0.54]
def controlar(l,m):
    k=m.get('k',0); m['k']=k+1
    if k<2: return [1.0,0.0]
    u=m.setdefault('u',[-1.32,0.653])
    if k<6: return list(u)
    e=[T[0]-l[0],T[1]-l[1]]
    for i in range(2):
        u[i]+=0.15*(Bi[i][0]*e[0]+Bi[i][1]*e[1])
    u[0]=max(-1.8,min(3,u[0])); u[1]=max(-3,min(3,u[1]))
    return list(u)