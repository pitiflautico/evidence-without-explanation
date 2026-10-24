Bi=[[-1.2/-2.074,0.55/-2.074],[1.0/-2.074,1.27/-2.074]]
T=[-0.39,0.54]
def controlar(l,m):
    u=m.setdefault('u',[-1.32,0.653])
    e=[T[0]-l[0],T[1]-l[1]]
    for i in range(2):
        u[i]+=0.25*(Bi[i][0]*e[0]+Bi[i][1]*e[1])
        u[i]=max(-3,min(3,u[i]))
    return list(u)