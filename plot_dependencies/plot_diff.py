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
parser.add_argument('-s', dest="save_plot", action=argparse.BooleanOptionalAction, help="Save plot to file")
parser.add_argument("-f1", dest="f1_name", type=str, help="The first file to plot")
parser.add_argument("-f2", dest="f2_name", type=str, help="The second file to plot")
parser.add_argument("-x", dest="x_lim", type=int, help="The x limit of the plot")
parser.add_argument("-y", dest="y_lim", type=int, help="The y limit of the plot")
args = parser.parse_args()

home = os.path.expanduser("~")
stats_dir = f"{home}/nec/gem5/plot_dependencies/stats" if "crd" in home else f"{home}/gem5/plot_dependencies/stats"
save_dir = f"{home}/Documents/y6s2/ma-TDT4900/diff_plots" if "crd" in home else f"{home}/diff_plots"

f1_name = args.f1_name if args.f1_name else "whet100B"
f2_name = args.f2_name if args.f2_name else "whet_art100B"

def make_cumul():
    df =     pd.read_csv(f"{stats_dir}/dist_dependencies_{f1_name}.csv")
    df_all = pd.read_csv(f"{stats_dir}/dist_dependencies_{f2_name}.csv")
    
    df = df.sort_values("delta")
    df_all = df_all.sort_values("delta")
    
    df["cum_num"] = df["num"].cumsum()
    df_all["cum_num"] = df_all["num"].cumsum()
    
    df["cum_pct"] = df["cum_num"] / df["num"].sum() * 100
    df_all["cum_pct"] = df_all["cum_num"] / df_all["num"].sum() * 100
    
    plt.plot(df["delta"], df["cum_pct"], alpha=1.0, label=f1_name)
    plt.plot(df_all["delta"], df_all["cum_pct"], alpha=1.0, color="orange", label=f2_name)
    if args.cumulog:
        plt.xscale("log") 
    
    plt.title(f"[diff] Cumulative graph for {f1_name} and {f2_name}")
    plt.xlabel("Delta (cycles)")
    plt.ylabel("Cumulative % of instructions")
    plt.legend(loc="upper left")
    plt.yticks(np.arange(0, 100+1, 10))
    x_lim = args.x_lim if args.x_lim else df["delta"].max()
    return (x_lim, 100, "cumul")


def make_hist():
    df =     pd.read_csv(f"{stats_dir}/dist_dependencies_{f1_name}.csv")
    df_all = pd.read_csv(f"{stats_dir}/dist_dependencies_{f2_name}.csv")

    delta_only = []
    all_delta_only = []
    
    x_lim = args.x_lim if args.x_lim else max(df["delta"].max(), df_all["delta"].max())
    y_lim = args.y_lim if args.y_lim else max(df["num"].max(), df_all["num"].max())
    
    for d, i in zip(df["delta"], df["num"]):
        if d <= x_lim:
            for _ in range(i):
                delta_only.append(d)
    delta_only = np.array(delta_only)
    
    for d, i in zip(df_all["delta"], df_all["num"]):
        if d <= x_lim:
            for _ in range(i):
                all_delta_only.append(d)
    all_delta_only = np.array(all_delta_only)
    
    all_bins = np.arange(all_delta_only.min(), all_delta_only.max() + 2) - 0.5
    all_counts, all_bins, _ = plt.hist(all_delta_only, bins=all_bins, color="orange", edgecolor="black", alpha=1.0, label=f2_name)
    
    bins = np.arange(delta_only.min(), delta_only.max() + 2) - 0.5
    counts, bins, _ = plt.hist(delta_only, bins=bins, edgecolor="black", alpha=1.0, label=f1_name)
    
    if args.histv_type:
        for count, x, all_count, all_x in zip(counts, bins, all_counts, all_bins):
            if x < x_lim and all_x < x_lim:
                if count != 0:
                    tx = round((int(all_count) - int(count))/int(count)*100)
                else:
                    tx = 0
                    
                if tx != 0:
                    plt.text(
                        x + (bins[1]-bins[0])/2,
                        0.3e6,
                        str(tx) + "%",
                        ha='center', va='bottom',
                        rotation=90,
                        fontsize=3
                    )
    
    plt.title(f"[diff] Histogram for {f1_name} and {f2_name}")
    plt.legend(loc="upper right")
    plt.xlabel("Delta (cycles)")
    plt.ylabel("Number of instructions")
    return (x_lim, y_lim, "hist")

if args.hist_type or args.histv_type:
    x_lim, y_lim, plt_type = make_hist()
elif args.cumul or args.cumulog:
    x_lim, y_lim, plt_type = make_cumul()
else:
    print("No valid plot type, exiting.")
    sys.exit(0)

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
            f"{save_dir}/{plt_type}_{f1_name}_{f2_name}.pdf",
            dpi=150,
            bbox_inches="tight",
            facecolor="white",
            orientation="landscape"
        )
    plt.show()
except KeyboardInterrupt:
    sys.exit(0)
