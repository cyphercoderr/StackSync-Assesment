from context import *

from pathlib import Path
import time

sf = PythonSafeEval.SafeEval(version="3.8", modules=["numpy"])

try:
    print(sf.eval(code='print("Hello World")').stdout)
    print(sf.execute_file(filename=Path(__file__).parent / "test_numpy.py").stdout)

    # benchmarking
    start_time = time.time()
    n = 100
    for i in range(0, n):
        sf.eval(code='print("Hello World {}")'.format(str(i)))
    print("{n} prints take {time} seconds ---".format(n=n, time=time.time() - start_time))
except:
    print("error")