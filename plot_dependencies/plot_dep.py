import matplotlib.pyplot as plt
import pandas as pd 
import numpy as np
import argparse
import signal
import sys
import os

signal.signal(signal.SIGINT, signal.SIG_DFL)

parser = argparse.ArgumentParser()
parser.add_argument("-hist",  dest="hist_type",  action=argparse.BooleanOptionalAction, help="Plot histogram. Default is scatter plot.")
parser.add_argument('-histv', dest="histv_type", action=argparse.BooleanOptionalAction, help="Plot histogram with num values on the bars.")
parser.add_argument('-cumul', dest="cumul", action=argparse.BooleanOptionalAction, help="Plot cumulative graph.")
parser.add_argument('-cumulog', dest="cumulog", action=argparse.BooleanOptionalAction, help="Plot cumulative graph with logarithmic scaling on the x graph.")
parser.add_argument('-all', dest="all_bench", action=argparse.BooleanOptionalAction, help="Overlay cumulative curves for every benchmark in the combined file.")
parser.add_argument('-geo', dest="geo", action=argparse.BooleanOptionalAction, help="Overlay the geometric-mean cumulative curve across all benchmarks. Combine with -all to draw it on top of the per-benchmark curves.")
parser.add_argument('-s', dest="save_plot", action=argparse.BooleanOptionalAction, help="Save plot to file")
parser.add_argument("-f", dest="file_name", type=str, help="The file to plot")
parser.add_argument("-x", dest="x_lim", type=int, help="The x limit of the plot")
parser.add_argument("-y", dest="y_lim", type=int, help="The y limit of the plot")
args = parser.parse_args()

home = os.path.expanduser("~")
stats_dir = f"{home}/nec/gem5/plot_dependencies/stats" if "crd" in home else f"{home}/gem5/plot_dependencies/stats"
save_dir = f"{home}/Documents/y6s2/ma-TDT4900" if "crd" in home else f"{home}/gem5/plot_dependencies/plots"

default_name = "all160" if (args.all_bench or args.geo) else "whet1B"
file_name = args.file_name if args.file_name else default_name

def make_cumul_all():
    df = pd.read_csv(f"{stats_dir}/dist_dependencies_{file_name}.csv")
    x_lim = args.x_lim if args.x_lim else df["delta"].max()
    # The default color cycle only has 10 colors, so with ~20 benchmarks the
    # colors wrap around. Keep colors but switch to a dashed line style once we
    # wrap, so every (color, style) combination is unique and identifiable.
    n_colors = len(plt.rcParams["axes.prop_cycle"])
    for i, (bench, g) in enumerate(df.groupby("bench")):
        g = g.sort_values("delta")
        cum_pct = g["num"].cumsum() / g["num"].sum() * 100
        linestyle = "-" if (i // n_colors) % 2 == 0 else "--"
        plt.plot(g["delta"], cum_pct, label=bench, linestyle=linestyle)
    if args.cumulog:
        plt.xscale("log")
    # plt.title("Cumulative dependency distance — all benchmarks (IQ=160)")
    plt.xlabel("Delta (cycles)")
    plt.ylabel("Cumulative % of dependencies")
    plt.yticks(np.arange(0, 100+1, 10))
    plt.legend(fontsize=7, ncol=2)
    return (x_lim, 100, "cumul_all")


def make_cumul_geo():
    # Independent graph: a single curve that is the geometric mean of the
    # per-benchmark cumulative curves. Each benchmark's curve is a step function
    # of delta, so evaluate them all on a shared delta grid (the union of every
    # benchmark's deltas, forward-filled), then take the geometric mean across
    # benchmarks at each delta.
    df = pd.read_csv(f"{stats_dir}/dist_dependencies_{file_name}.csv")
    x_lim = args.x_lim if args.x_lim else df["delta"].max()
    grid = np.sort(df["delta"].unique())
    curves = []
    for _, g in df.groupby("bench"):
        s = g.groupby("delta")["num"].sum().sort_index()
        cum = s.cumsum() / s.sum() * 100
        curves.append(cum.reindex(grid, method="ffill").fillna(0).values)
    curves = np.array(curves)
    with np.errstate(divide="ignore"):       # log(0) -> -inf -> geo 0
        geo = np.exp(np.log(curves).mean(axis=0))
    # Dump the curve as CSV (delta,cum_percentage) next to the plot output.
    csv_dir = f"{save_dir}/cumul_geo_plots"
    os.makedirs(csv_dir, exist_ok=True)
    csv_path = f"{csv_dir}/{file_name}_cumul_geo.csv"
    pd.DataFrame({"delta": grid, "cum_percentage": geo}).to_csv(
        csv_path, index=False, float_format="%.2f")
    print(f"Geomean curve written to {csv_path}")
    plt.plot(grid, geo, label="geomean", color="black")
    if args.cumulog:
        plt.xscale("log")
    # plt.title("Cumulative dependency distance — geomean (IQ=160)")
    plt.xlabel("Delta (cycles)")
    plt.ylabel("Cumulative % of dependencies")
    plt.yticks(np.arange(0, 100+1, 10))
    plt.legend(fontsize=7)
    return (x_lim, 100, "cumul_geo")


def make_cumul():
    df = pd.read_csv(f"{stats_dir}/dist_dependencies_{file_name}.csv")
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
    df = pd.read_csv(f"{stats_dir}/dist_dependencies_{file_name}.csv")
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
    df = pd.read_csv(f"{stats_dir}/dist_dependencies_{file_name}.csv").to_numpy()
    delta = np.array([e[0] for e in df])
    num = np.array([e[1] for e in df])
    plt.scatter(delta, num)
    
    plt.title(f"Scatter-plot for {file_name}")
    plt.xlabel("Delta (cycles)")
    plt.ylabel("Number of instructions")
    x_lim = args.x_lim if args.x_lim else delta.max()
    y_lim = args.y_lim if args.y_lim else num.max()
    return (x_lim, y_lim, "scatter")

if args.geo:
    x_lim, y_lim, plt_type = make_cumul_geo()
elif args.all_bench:
    x_lim, y_lim, plt_type = make_cumul_all()
elif args.hist_type or args.histv_type:
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
        os.makedirs(f"{save_dir}/{plt_type}_plots", exist_ok=True)
        plt.savefig(
            f"{save_dir}/{plt_type}_plots/{file_name}_{plt_type}.pdf",
            # f"/home/crd/Documents/y6s1/project-TDT4501/{file_name}_{plt_type}_full.pdf",
            dpi=150,
            bbox_inches="tight",
            facecolor="white",
            orientation="landscape"
        )
    plt.show()
except KeyboardInterrupt:
    sys.exit(0)
