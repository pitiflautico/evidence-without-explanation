
def controlar(l, m):
    T=[0.85,-0.37]
    a,b,c,d=0.62,-0.7,-1.22,-0.67
    det=a*d-b*c
    e=[T[0]-l[0],T[1]-l[1]]
    I=m.get('I',[0.0,0.0])
    n=m.get('n',0)+1; m['n']=n
    if n>4:
        I=[I[0]+0.15*e[0],I[1]+0.15*e[1]]
    m['I']=I
    dy=[1.24+I[0],-1.24+I[1]]
    u1=(d*dy[0]-b*dy[1])/det
    u2=(-c*dy[0]+a*dy[1])/det
    return [max(-3,min(3,u1)),max(-3,min(3,u2))]
