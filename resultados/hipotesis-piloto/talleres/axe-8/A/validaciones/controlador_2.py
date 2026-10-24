import numpy as np
B=np.array([[0.13,0.12],[-0.06,0.09]]);Bi=np.linalg.inv(B)
def controlar(l, m):
    t=np.array([-0.35,-1.35]);e=np.array(l)-t
    m['i']=m.get('i',np.zeros(2))+e
    v=-0.12*e-0.01*m['i']
    u=Bi@v
    return [float(np.clip(x,-3,3)) for x in u]