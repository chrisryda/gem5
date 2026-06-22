import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
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
parser.add_argument('-srcs', dest="srcs", action=argparse.BooleanOptionalAction, help="Plot the per-instruction outstanding-source-count distribution (dist_outstanding_srcs_*.csv, IQ=160/DIQ=0 baseline) as a stacked %% bar per benchmark.")
parser.add_argument('-nonready', dest="nonready", action=argparse.BooleanOptionalAction, help="With -srcs: restrict to non-ready instructions (>=1 outstanding source); the k=1 segment is then the DIQ single-link target share.")
parser.add_argument('-s', dest="save_plot", action=argparse.BooleanOptionalAction, help="Save plot to file")
parser.add_argument("-f", dest="file_name", type=str, help="The file to plot")
parser.add_argument("-x", dest="x_lim", type=int, help="The x limit of the plot")
parser.add_argument("-y", dest="y_lim", type=int, help="The y limit of the plot")
args = parser.parse_args()

home = os.path.expanduser("~")
stats_dir = f"{home}/nec/gem5/plot_dependencies/stats" if "crd" in home else f"{home}/gem5/plot_dependencies/stats"
save_dir = f"{home}/Documents/y6s2/ma-TDT4900" if "crd" in home else f"{home}/gem5/plot_dependencies/plots"

default_name = "all160" if (args.all_bench or args.geo or args.srcs) else "whet1B"
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


def make_outstanding():
    # New measurement, collected only from the IQ=160/DIQ=0 baseline sims (the
    # DIQ characterization gate): counted once per instruction AT RENAME (first
    # rename pass, rename.cc renameSrcRegs), how many of its source operands
    # still had an in-flight producer.  CSV schema is
    #   bench,outstanding_srcs,num_insts
    # with outstanding_srcs = k (0,1,2,...) and num_insts = number of renamed
    # instructions that had exactly k outstanding sources.  k==1 is the DIQ's
    # target population: a single producer->consumer back-pointer suffices, so a
    # large k==1 share among *non-ready* (k>=1) instructions validates the DIQ.
    df = pd.read_csv(f"{stats_dir}/dist_outstanding_srcs_{file_name}.csv")
    # collect-outstanding appends suite-average summary rows (pooled_pct /
    # arithmean_pct / geomean_pct, holding PERCENTAGES not counts).  Drop them so
    # they are not drawn as extra bars -- the pooled summary bar is recomputed
    # below from the per-benchmark counts (self-contained).  "pooled" kept for
    # backward-compat with the earlier summed-count rows.
    df = df[~df["bench"].isin(
        ["pooled", "pooled_pct", "arithmean_pct", "geomean_pct",
         "pooled_pct_nonready", "arithmean_pct_nonready", "geomean_pct_nonready"])]

    # Stacked distribution.  Cap the (rare) long tail into a single "cap+" bucket
    # so the bars stay legible; -x overrides the cap (default 5).
    cap = args.x_lim if args.x_lim else 5
    df = df.copy()
    df["k"] = df["outstanding_srcs"].clip(upper=cap)
    piv = df.groupby(["bench", "k"])["num_insts"].sum().unstack(fill_value=0)
    for k in range(cap + 1):                       # guarantee every column 0..cap
        if k not in piv.columns:
            piv[k] = 0
    piv = piv[sorted(piv.columns)]

    denom = "renamed"
    if args.nonready:                              # drop ready insts (k==0)
        piv = piv.drop(columns=[0], errors="ignore")
        denom = "non-ready"

    # Express each bench's raw counts as % of its OWN instruction total.  The k
    # buckets partition the bench, so this is exact (sums to 100, nothing
    # stretched) -- it's the real per-bench distribution, just in % not counts.
    pct = piv.div(piv.sum(axis=1), axis=0) * 100

    # Single-outstanding-source (k==1) share in the current denominator, per
    # benchmark plus the three suite-level averages.  POOLED is what the summary
    # bar shows (instruction-weighted fraction over the whole suite); the other
    # two are printed for reference.
    share     = pct[1]
    pooled_k1 = piv[1].sum() / piv.values.sum() * 100
    amean_k1  = share.mean()
    geo_k1    = np.exp(np.log(share.replace(0, np.nan)).mean())
    print(f"single-outstanding-source (k=1) share among "
          f"{'non-ready (k>=1)' if args.nonready else 'all renamed'} instructions:")
    for b in share.sort_index().index:
        print(f"  {b:<14s} {share[b]:5.1f}%")
    print(f"  {'POOLED':<14s} {pooled_k1:5.1f}%   (instruction-weighted; the summary bar)")
    print(f"  {'arith-mean':<14s} {amean_k1:5.1f}%")
    print(f"  {'geomean':<14s} {geo_k1:5.1f}%")

    benches = list(pct.index)
    x = np.arange(len(benches))
    bottom = np.zeros(len(benches))
    # Colour keyed to the k value (not column position) so the k==1 segment is
    # the same hue with or without k==0 present (default vs -nonready stay comparable).
    colors = {k: plt.cm.viridis(0.1 + 0.8 * (k / cap)) for k in range(cap + 1)}
    for k in pct.columns:
        label = f"{int(k)}+" if k == cap else f"{int(k)}"
        plt.bar(x, pct[k].values, bottom=bottom, color=colors[k],
                edgecolor="black", linewidth=0.3, label=label, zorder=3)
        bottom += pct[k].values

    # Pooled summary bar, drawn to the right with a gap.  Each segment is the
    # instruction-weighted share over the whole suite: sum the raw counts across
    # benchmarks, then normalize.  It is a genuine distribution, so it sums to
    # 100% exactly like the per-benchmark bars, and the k==1 height is the
    # fraction of all (current-denominator) instructions with one outstanding src.
    pooled = piv.sum(axis=0)
    pooled = pooled / pooled.sum() * 100
    gx = len(benches) + 0.8
    gbottom = 0.0
    for k in pct.columns:
        plt.bar(gx, pooled[k], bottom=gbottom, color=colors[k],
                edgecolor="black", linewidth=0.3, zorder=3)
        gbottom += pooled[k]
    plt.axvline(len(benches) - 0.1, color="0.6", linewidth=0.8,
                linestyle="--", zorder=1)

    plt.xticks(list(x) + [gx], benches + ["pooled"], rotation=45, ha="right",
               rotation_mode="anchor", fontsize=7)
    plt.gca().get_xticklabels()[-1].set_fontweight("bold")
    plt.ylabel(f"% of {denom} instructions")
    plt.ylim(0, 100)
    plt.yticks(np.arange(0, 100 + 1, 10))

    # Horizontal legend across the top, prefixed inline by a label.  The prefix
    # is a marker-less proxy handle so it flows on the same row as the colour
    # swatches: "No. outstanding sources:  [c0] 0  [c1] 1  ...".
    handles, _ = plt.gca().get_legend_handles_labels()
    prefix = Line2D([], [], marker="none", linestyle="none",
                    label="No. outstanding sources:")
    leg = plt.legend(handles=[prefix] + handles, ncol=len(handles) + 1,
                     loc="lower center", bbox_to_anchor=(0.5, 1.0),
                     frameon=False, fontsize=8, handlelength=1.1,
                     handletextpad=0.4, columnspacing=1.1, borderaxespad=0.4)
    leg.get_texts()[0].set_fontweight("bold")

    plt_type = "outstanding_nonready" if args.nonready else "outstanding"
    return (None, None, plt_type)


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

if args.srcs:
    x_lim, y_lim, plt_type = make_outstanding()
elif args.geo:
    x_lim, y_lim, plt_type = make_cumul_geo()
elif args.all_bench:
    x_lim, y_lim, plt_type = make_cumul_all()
elif args.hist_type or args.histv_type:
    x_lim, y_lim, plt_type = make_hist()
elif args.cumul or args.cumulog:
    x_lim, y_lim, plt_type = make_cumul()
else:
    x_lim, y_lim, plt_type = make_scatter()

# The numeric-x reformatting below only applies to the delta-based plots; the
# outstanding-source plot uses a categorical (per-benchmark) x-axis set above.
if not args.srcs:
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
