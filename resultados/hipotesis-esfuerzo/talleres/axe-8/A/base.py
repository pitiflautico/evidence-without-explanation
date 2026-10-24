
import numpy as np, json
U=[];Y=[]
for l in open('exploracion.jsonl'):
    d=json.loads(l); U+=d['secuencia']; Y+=d['lecturas']
U=np.array(U);Y=np.array(Y)
Yf=np.vstack([[0.688,-0.725],Y])
np.set_printoptions(precision=3,suppress=True,linewidth=150)
