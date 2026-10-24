def controlar(l, m):
    t=[-1.06,0.44]
    w=m.get('w',0.0)
    w+=0.8*(t[1]-l[1])
    w=max(-5,min(5,w))
    m['w']=w
    v=1.0*(t[0]-l[0])+m.get('vi',0.0)
    m['vi']=max(-2,min(2,m.get('vi',0.0)+0.05*(t[0]-l[0])))
    u1=max(-3,min(3,(w+v)/2)); u2=max(-3,min(3,(w-v)/2))
    return [u1,u2]