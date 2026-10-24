def controlar(l, m):
    y1,y2=l
    s=m.get('s',0.16)
    s+=0.5*(0.44-y2)/0.55
    s=max(-3,min(3,s)); m['s']=s
    r=0.5*(-1.06-y1)
    a=(r+0.91*s)/1.48
    a=max(-3,min(3,a))
    return [a, max(-3,min(3,s-a))]