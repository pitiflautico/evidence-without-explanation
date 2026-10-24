
def controlar(l,m):
    u1=m.get('u1',2.4);u2=m.get('u2',0.0)
    u1+=0.25*(1.48-l[0])
    if l[1]>-0.38: u2-=0.1
    u1=max(-3,min(3,u1));u2=max(-3,min(3,u2))
    m['u1']=u1;m['u2']=u2
    return [u1,u2]
