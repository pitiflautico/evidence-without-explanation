def controlar(l, m):
    u1=m.get('u1',0.0); u2=m.get('u2',3.0)
    e1=l[0]+0.13; e2=l[1]+1.31
    # du = -k*inv(J)*e, inv(J)=[[-0.932,1.05],[-0.711,-1.016]]
    k=0.5
    u1+=-k*(-0.932*e1+1.05*e2); u2+=-k*(-0.711*e1-1.016*e2)
    u1=max(-3,min(3,u1)); u2=max(-3,min(3,u2))
    m['u1']=u1; m['u2']=u2
    return [u1,u2]