import json,sys
sys.path[:0]=['.','tests']
from evaluators.candidate import build_circuits, parse_schedule
from evaluators.noise import add_noise
from evaluators.tasks import build_code, get_task
code,_=build_code(get_task('gross-dcirc'),None)
spec=parse_schedule(json.load(open('search/experiments/e024a/cs_P18_H24.json')))
c=add_noise(build_circuits(spec.canonical(),code,1)['Z'],'sd6',1e-3)
co=c.get_detector_coordinates()
print(len(co), list(co.items())[:3], list(co.items())[-3:])
print(set(type(x).__name__ for x in c.flattened()))
from collections import Counter
print(Counter(i.name for i in c.flattened()))
print(code.HZ.shape, code.LZ.shape)
