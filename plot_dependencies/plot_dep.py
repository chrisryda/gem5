import matplotlib.pyplot as plt
import pandas as pd 
import numpy as np
import argparse
import signal
import sys

signal.signal(signal.SIGINT, signal.SIG_DFL)

parser = argparse.ArgumentParser()
parser.add_argument("-t", dest="plt_type", type=str, help="The type of plot {sca, hist, sorted}")
parser.add_argument("-f", dest="file_name", type=str, help="The file to plot {whet<1,5,10,15,20>}")
parser.add_argument('-s', dest="save_plot", action=argparse.BooleanOptionalAction)
parser.add_argument('-v', dest="add_values", action=argparse.BooleanOptionalAction)
args = parser.parse_args()

plt_type = args.plt_type if args.plt_type else "scatter"
file_name = args.file_name if args.file_name else "whet1B"

def make_hist() -> None:
    delta_only = []
    for d, i in zip(delta, instructions):
        for _ in range(i):
            delta_only.append(d)
    delta_only = np.array(delta_only)
    counts, bins, _ = plt.hist(delta_only, bins="auto", edgecolor="black", alpha=0.9)
    
    if args.add_values:
        for count, x in zip(counts, bins):
            if count != 0:
                plt.text(
                    x + (bins[1]-bins[0])/2,  # midpoint of each bin
                    20,                       # height (where text goes)
                    str(int(count)),          # text label
                    ha='center', va='bottom', # text alignment
                )
    return
    
def make_sorted() -> None:
    sort = df[df[:, 0].argsort()]
    x = np.array([e[0] for e in sort])
    y = np.array([e[1] for e in sort])
    a, b, c = np.polyfit(x, y, 2)
    line = a*x*x + b*x + c
    plt.plot(x, y, line, color="red")
    return
    
df = pd.read_csv(f"plot_dependencies/stats/dist_dependencies_{file_name}.csv").to_numpy()
delta = np.array([e[0] for e in df])
instructions = np.array([e[1] for e in df])
match plt_type:
    case "scatter":
        plt.scatter(delta, instructions)
        plt.title(f"Scatter-plot for {file_name}")
    case "hist":
        make_hist()
        plt.title(f"Histogram for {file_name}")
    case "sorted":
        plt.title(f"<something>-plot for {file_name}")
        make_sorted()
    case _:
        print("Invalid option, exiting")
        sys.exit(0)

plt.xlabel("Delta (ticks)")
plt.ylabel("Number of instructions")
plt.grid(True, linestyle="--", alpha=0.5)
try:
    if args.save_plot:
        plt.savefig(
            f"/home/crd/Documents/y6s1/project-TDT4501/{file_name}_{plt_type}.pdf",
            dpi=300,
            bbox_inches="tight",
            facecolor="white"
        )
    plt.show()
except KeyboardInterrupt:
    sys.exit(0)
