import matplotlib.pyplot as plt
import pandas as pd 
import numpy as np
import argparse
import signal
import sys

signal.signal(signal.SIGINT, signal.SIG_DFL)

parser = argparse.ArgumentParser()
parser.add_argument('-t', dest='plt_type', type=str, help='The type of plot {sca, hist, sorted}')
args = parser.parse_args()

df = pd.read_csv("dist_dependencies.csv").to_numpy()
delta = np.array([e[0] for e in df])
instructions = np.array([e[1] for e in df])

plt_type = args.plt_type if args.plt_type else "scatter"
match plt_type:
    case 'scatter':
        plt.scatter(delta, instructions)

    case 'hist':
        plt.hist(delta, bins='auto', edgecolor='black', alpha=0.9)
                
    case 'sorted':
        sort = df[df[:, 0].argsort()]
        x = np.array([e[0] for e in sort])
        y = np.array([e[1] for e in sort])
        a, b, c = np.polyfit(x, y, 2)
        line = a*x*x + b*x + c
        plt.plot(x, y, line, color='red')
        
    case _:
        print("Invalid option, exiting")
        sys.exit(0)
        
plt.xlabel("Delta (ticks)")
plt.ylabel("Number of instructions")
plt.grid(True, linestyle='--', alpha=0.5)
try:
    plt.show()
except KeyboardInterrupt:
    sys.exit(0)
