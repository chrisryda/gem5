import matplotlib.pyplot as plt
import pandas as pd 
import numpy as np
import argparse
import signal
import sys

signal.signal(signal.SIGINT, signal.SIG_DFL)

parser = argparse.ArgumentParser()
parser.add_argument("-hist",  dest="hist_type",  action=argparse.BooleanOptionalAction, help="Plot histogram. Default is scatter plot.")
parser.add_argument('-histv', dest="histv_type", action=argparse.BooleanOptionalAction, help="Plot histogram with num values on the bars.")
parser.add_argument('-s', dest="save_plot", action=argparse.BooleanOptionalAction, help="Save plot to file")
parser.add_argument("-f", dest="file_name", type=str, help="The file to plot")
parser.add_argument("-x", dest="x_lim", type=int, help="The x limit of the plot")
args = parser.parse_args()

def make_hist() -> None:
    delta_only = []
    for d, i in zip(delta, instructions):
        if d <= x_lim:
            for _ in range(i):
                delta_only.append(d)
    delta_only = np.array(delta_only)
    
    bins = np.arange(delta_only.min(), delta_only.max() + 2) - 0.5
    counts, bins, _ = plt.hist(delta_only, bins=bins, edgecolor="black", alpha=0.9)
    
    if args.histv_type:
        for count, x in zip(counts, bins):
            if count != 0:
                plt.text(
                    x + (bins[1]-bins[0])/2,  # midpoint of each bin
                    1000,                     # height (where text goes)
                    str(int(count)),          # text label
                    ha='center', va='bottom', # text alignment
                    rotation=90,
                    # fontsize=3
                )
    return

file_name = args.file_name if args.file_name else "whet1B"
df = pd.read_csv(f"plot_dependencies/stats/dist_dependencies_{file_name}.csv").to_numpy()
delta = np.array([e[0] for e in df])
instructions = np.array([e[1] for e in df])
x_lim = args.x_lim if args.x_lim else delta.max() 

if args.hist_type or args.histv_type:
    make_hist()
    plt_type = "hist"
    plt.title(f"Histogram for {file_name}")
else:
    plt.scatter(delta, instructions)
    plt_type = "scatter"
    plt.title(f"Scatter-plot for {file_name}")

plt.xlabel("Delta (cycles)")
plt.ylabel("Number of instructions")
plt.xlim((-0.5, (x_lim+0.5)))
plt.grid(True, linestyle="--", alpha=0.5)
try:
    if args.save_plot:
        plt.savefig(
            f"/home/crd/Documents/y6s1/project-TDT4501/{file_name}_{plt_type}.pdf",
            dpi=150,
            bbox_inches="tight",
            facecolor="white",
            orientation="landscape"
        )
    plt.show()
except KeyboardInterrupt:
    sys.exit(0)
