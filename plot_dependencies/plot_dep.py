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
parser.add_argument('-cumul', dest="cumul", action=argparse.BooleanOptionalAction, help="Plot cumulative graph.")
parser.add_argument('-cumulog', dest="cumulog", action=argparse.BooleanOptionalAction, help="Plot cumulative graph with logarithmic scaling on the x graph.")
parser.add_argument('-s', dest="save_plot", action=argparse.BooleanOptionalAction, help="Save plot to file")
parser.add_argument("-f", dest="file_name", type=str, help="The file to plot")
parser.add_argument("-x", dest="x_lim", type=int, help="The x limit of the plot")
parser.add_argument("-y", dest="y_lim", type=int, help="The y limit of the plot")
args = parser.parse_args()

file_name = args.file_name if args.file_name else "whet1B"

def make_cumul():
    df = pd.read_csv(f"/home/crd/nec/gem5/plot_dependencies/stats/dist_dependencies_{file_name}.csv")
    df = df.sort_values("delta")
    df["cum_num"] = df["num"].cumsum()
    df["cum_pct"] = df["cum_num"] / df["num"].sum() * 100
    plt.plot(df["delta"], df["cum_pct"])
    if args.cumulog:
        plt.xscale("log") 
    
    plt.title(f"Cumulative graph for {file_name}")
    plt.xlabel("Delta (cycles)")
    plt.ylabel("Cumulative % of instructions")
    plt.yticks(np.arange(0, 100+1, 10))
    x_lim = args.x_lim if args.x_lim else df["delta"].max()
    return (x_lim, 100, "cumul")


def make_hist():
    df = pd.read_csv(f"/home/crd/nec/gem5/plot_dependencies/stats/dist_dependencies_{file_name}.csv")
    delta_only = []
    x_lim = args.x_lim if args.x_lim else df["delta"].max()
    y_lim = args.y_lim if args.y_lim else df["num"].max()
    for d, i in zip(df["delta"], df["num"]):
        if d <= x_lim:
            for _ in range(i):
                delta_only.append(d)
    delta_only = np.array(delta_only)
    
    bins = np.arange(delta_only.min(), delta_only.max() + 2) - 0.5
    counts, bins, _ = plt.hist(delta_only, bins=bins, edgecolor="black", alpha=1.0)
    
    if args.histv_type:
        for count, x in zip(counts, bins):
            if x < x_lim and count != 0:
                if args.save_plot and count < 0.5e6:
                    height = 20_000
                elif (count < y_lim):
                    height = 0.5*count    
                else:
                    height = 0.8*y_lim
                    
                plt.text(
                    x + (bins[1]-bins[0])/2,  # midpoint of each bin
                    height,                   # height (where text goes)
                    str(int(count)),          # text label
                    ha='center', va='bottom', # text alignment
                    rotation=90,
                    # fontsize=3
                )
    
    plt.title(f"Histogram for {file_name}")
    plt.xlabel("Delta (cycles)")
    plt.ylabel("Number of instructions")
    return (x_lim, y_lim, "hist")

def make_scatter():
    df = pd.read_csv(f"/home/crd/nec/gem5/plot_dependencies/stats/dist_dependencies_{file_name}.csv").to_numpy()
    delta = np.array([e[0] for e in df])
    num = np.array([e[1] for e in df])
    plt.scatter(delta, num)
    
    plt.title(f"Scatter-plot for {file_name}")
    plt.xlabel("Delta (cycles)")
    plt.ylabel("Number of instructions")
    x_lim = args.x_lim if args.x_lim else delta.max()
    y_lim = args.y_lim if args.y_lim else num.max()
    return (x_lim, y_lim, "scatter")

if args.hist_type or args.histv_type:
    x_lim, y_lim, plt_type = make_hist()
elif args.cumul or args.cumulog:
    x_lim, y_lim, plt_type = make_cumul()
else:
    x_lim, y_lim, plt_type = make_scatter()

if x_lim <= 10:
    plt.xticks(np.arange(0, (x_lim+1), 1))
elif x_lim <= 100:
    plt.xticks(np.arange(0, (x_lim+1), 5))

plt.xlim((-0.5, (x_lim+0.5)))
plt.ylim((-0.5, y_lim))
plt.grid(True, linestyle="--", alpha=0.5)
try:
    if args.save_plot:
        plt.savefig(
            f"/home/crd/Documents/y6s1/project-TDT4501/{plt_type}_plots/{file_name}_{plt_type}.pdf",
            # f"/home/crd/Documents/y6s1/project-TDT4501/{file_name}_{plt_type}_full.pdf",
            dpi=150,
            bbox_inches="tight",
            facecolor="white",
            orientation="landscape"
        )
    plt.show()
except KeyboardInterrupt:
    sys.exit(0)
