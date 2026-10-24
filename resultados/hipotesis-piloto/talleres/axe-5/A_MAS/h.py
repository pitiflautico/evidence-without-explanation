import json,numpy as np
S=[];Yl=[]
for l in open('exploracion.jsonl'):
  d=json.loads(l)
  if d.get('reiniciar'): S=[];Yl=[]
  S+=d['secuencia'];Yl+=d['lecturas']
S=np.array(S);Yl=np.array(Yl)
