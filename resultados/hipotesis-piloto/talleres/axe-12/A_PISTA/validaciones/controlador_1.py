def controlar(l, m):
    a=m.get('a',0.0); b=m.get('b',0.0)
    e1=l[0]+0.98; e2=0.71-l[1]
    a+=0.1*e1; b+=0.1*e2
    a=max(-1,min(1,a)); b=max(-1,min(1,b))
    m['a']=a; m['b']=b
    u1=1.5+a; u2=1.9+a+b
    return [max(-3,min(3,u1)),max(-3,min(3,u2))]