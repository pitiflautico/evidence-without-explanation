
def controlar(lecturas, memoria):
    T=(0.33,0.7)
    Bi=((-5.8,4.5),(-4.1,-2.8))
    I=memoria.get("I",[0.0,0.0])
    e=[T[i]-lecturas[i] for i in range(2)]
    I=[max(-20.0,min(20.0,I[i]+e[i])) for i in range(2)]
    memoria["I"]=I
    v=[0.5*e[i]+0.1*I[i] for i in range(2)]
    u=[Bi[j][0]*v[0]+Bi[j][1]*v[1] for j in range(2)]
    return [max(-3.0,min(3.0,x)) for x in u]
