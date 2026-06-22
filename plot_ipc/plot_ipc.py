import re
import csv
import sys
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
import numpy as np

RESULTS_FILE = Path(__file__).parent.parent / "iq-sweep-all.txt"
CSV_OUT      = Path(__file__).parent / "iq_sweep_ipc.csv"
PLOT_DIR     = Path(__file__).parent

BENCHMARK_ORDER = [
    "whetstone",
    "perlbench_s",   # 600
    "gcc_s",         # 602
    "bwaves_s",      # 603
    "mcf_s",         # 605
    "cactuBSSN_s",   # 607
    "lbm_s",         # 619
    "omnetpp_s",     # 620
    "wrf_s",         # 621
    "xalancbmk_s",   # 623
    "x264_s",        # 625
    "cam4_s",        # 627
    "pop2_s",        # 628
    "deepsjeng_s",   # 631
    "imagick_s",     # 638
    "leela_s",       # 641
    "nab_s",         # 644
    "exchange2_s",   # 648
    "fotonik3d_s",   # 649
    "roms_s",        # 654
    "xz_s",          # 657
]

# Minimum IPC range before colour scaling is considered meaningful.
# Values within this band are treated as identical (mapped to neutral 0.5).
COLOR_MIN_RANGE = 0.01


def _ctx_from_runtag(runtag: str) -> str:
    """Strip the _iqN and _diqN components from a SIM_TAG to get run context."""
    ctx = re.sub(r'_iq\d+', '', runtag)
    ctx = re.sub(r'_diq\d+', '', ctx)
    return ctx



def parse_results(path):
    records, current = [], {}
    with open(path) as f:
        for raw in f:
            line = raw.strip()

            m = re.match(r'^(\w+)\s+IQ=(\d+)\s+DIQ=(\d+)\s+SIM_TAG=(\d+/\d+)(?:\s+RUNTAG=(\S+))?$', line)
            if m:
                runtag = m.group(5) or ""
                current = {
                    "benchmark": m.group(1),
                    "iq":  int(m.group(2)),
                    "diq": int(m.group(3)),
                    "config": m.group(4),
                    "runtag": runtag,
                    "ctx": _ctx_from_runtag(runtag),
                }
                continue

            for key, pattern in [
                ("ipc",             r"core\.ipc\s+([\d.]+)"),
                ("cpi",             r"core\.cpi\s+([\d.]+)"),
                ("instsAdded",      r"core\.instsAdded\s+(\d+)"),
                ("deltaInstsAdded", r"core\.deltaInstsAdded\s+(\d+)"),
                ("iqFullEvents",    r"iqFullEvents\s+(\d+)"),
            ]:
                m = re.search(pattern, line)
                if m and current:
                    current[key] = float(m.group(1)) if "." in m.group(1) else int(m.group(1))

            if "End Simulation Statistics" in line and "ipc" in current:
                current.setdefault("deltaInstsAdded", 0)
                records.append(current)
                current = {}
    return records


def write_csv(records, path):
    fields = ["benchmark", "config", "iq", "diq", "ctx",
              "ipc", "cpi", "instsAdded", "deltaInstsAdded", "iqFullEvents"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in records:
            w.writerow({k: r.get(k, "") for k in fields})


def _label_bars(ax, bar_container, fmt="{:.3f}"):
    for bar in bar_container:
        h = bar.get_height()
        if not np.isnan(h):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h, fmt.format(h),
                ha="center", va="bottom",
                rotation=90, fontsize=6,
            )


def _benchmarks(records):
    return [b for b in BENCHMARK_ORDER
            if any(r["benchmark"] == b for r in records)]


def _file_ctx(records):
    """Return a context string for use in saved filenames."""
    ctxs = sorted(set(r["ctx"] for r in records if r.get("ctx")))
    return "+".join(ctxs) if ctxs else "unknown"


# ---------------------------------------------------------------------------
# Line chart — one figure per benchmark
# ---------------------------------------------------------------------------
def plot_lines(records):
    data      = {(r["iq"], r["diq"], r["benchmark"]): r["ipc"] for r in records}
    ctx_map   = {r["iq"]: r["ctx"] for r in records}
    iq_sizes  = sorted(set(r["iq"]  for r in records))
    diq_sizes = sorted(set(r["diq"] for r in records))

    # tab10/tab20 give maximally distinct categorical colors
    palette = list(plt.cm.tab10.colors) + list(plt.cm.tab10.colors)
    colors = {d: palette[i] for i, d in enumerate(diq_sizes)}

    figs = []
    for bench in _benchmarks(records):
        fig, ax = plt.subplots(figsize=(10, 5))

        for diq in diq_sizes:
            xs = [iq for iq in iq_sizes if (iq, diq, bench) in data]
            ys = [data[(iq, diq, bench)] for iq in xs]
            if not xs:
                continue
            ax.plot(xs, ys, marker="o", markersize=4,
                    linewidth=2.2 if diq == 0 else 1.3,
                    linestyle="--" if diq == 0 else "-",
                    color=colors[diq], label=f"DIQ={diq}")
            for x, y in zip(xs, ys):
                ax.text(x, y, f"{y:.3f}",
                        ha="center", va="bottom", rotation=90, fontsize=5)

        ctxs_str = ", ".join(sorted(set(ctx_map.values())))
        ax.set_title(f"{bench}  ({ctxs_str})" if ctxs_str else bench)
        ax.set_xlabel("IQ size")
        ax.set_ylabel("IPC")
        ax.set_xticks(iq_sizes)
        ax.set_xticklabels([str(iq) for iq in iq_sizes], fontsize=7)
        ax.margins(y=0.20)
        ax.legend(fontsize=7, ncol=2)
        ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
        ax.yaxis.get_major_formatter().set_useOffset(False)
        ax.ticklabel_format(useOffset=False, style="plain", axis="y")
        ax.grid(axis="both", which="major", linestyle="--", alpha=0.35)
        fig.tight_layout()
        figs.append((bench, fig))

    return figs


# ---------------------------------------------------------------------------
# Bar chart — one figure per benchmark (normalised + absolute side by side)
# ---------------------------------------------------------------------------
def plot_bars(records, baseline_cfg="160/0", additive_cfg="120/80"):
    data       = {(r["config"], r["benchmark"]): r["ipc"] for r in records}
    ctx_map    = {r["config"]: r["ctx"] for r in records}
    configs    = sorted(set(r["config"] for r in records), key=lambda c: (int(c.split("/")[0]), int(c.split("/")[1])))
    cfg_labels = list(configs)
    colors     = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    sep_x      = configs.index(additive_cfg) - 0.5 if additive_cfg in configs else None

    def _sep(ax):
        if sep_x is not None:
            ax.axvline(sep_x, color="gray", linewidth=1.2, linestyle=":")
            ax.text(sep_x + 0.05, ax.get_ylim()[1] * 0.97, "additive →", fontsize=7, color="gray", va="top")

    x = np.arange(len(configs))
    width = 0.20

    figs = []
    for i, bench in enumerate(_benchmarks(records)):
        base  = data.get((baseline_cfg, bench), 1.0)
        color = colors[i % len(colors)]

        fig, axes = plt.subplots(1, 2, figsize=(12, 4))

        ax = axes[0]
        norm_vals = [data.get((c, bench), float("nan")) / base for c in configs]
        bars = ax.bar(x, norm_vals, width, color=color)
        _label_bars(ax, bars)
        ax.axhline(1.0, color="black", linewidth=0.9, linestyle="--")
        ax.set_xticks(x)
        ax.set_xticklabels(cfg_labels, rotation=45, ha="right")
        ax.set_xlabel("IQ / DIQ configuration")
        ax.set_ylabel(f"Normalized IPC  (baseline = {baseline_cfg})")
        ax.set_title("Relative IPC")
        ax.margins(y=0.15)
        ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
        ax.grid(axis="y", linestyle="--", alpha=0.35)
        _sep(ax)

        ax = axes[1]
        abs_vals = [data.get((c, bench), float("nan")) for c in configs]
        bars = ax.bar(x, abs_vals, width, color=color)
        _label_bars(ax, bars)
        ax.set_xticks(x)
        ax.set_xticklabels(cfg_labels, rotation=45, ha="right")
        ax.set_xlabel("IQ / DIQ configuration")
        ax.set_ylabel("IPC")
        ax.set_title("Absolute IPC")
        ax.margins(y=0.15)
        ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
        ax.grid(axis="y", linestyle="--", alpha=0.35)
        _sep(ax)

        unique_ctxs = sorted(set(ctx_map.values()))
        ctx_str = "  ".join(unique_ctxs)
        fig.suptitle(f"{bench}  {ctx_str}" if ctx_str else bench, fontsize=13)
        fig.tight_layout()
        figs.append((bench, fig))

    return figs


# ---------------------------------------------------------------------------
# Table — one figure per benchmark
# ---------------------------------------------------------------------------
def plot_table(records):
    data      = {(r["iq"], r["diq"], r["benchmark"]): r["ipc"] for r in records}
    ctx_map   = {r["iq"]: r["ctx"] for r in records}
    iq_sizes  = sorted(set(r["iq"]  for r in records))
    diq_sizes = sorted(set(r["diq"] for r in records))

    cmap     = plt.cm.RdYlGn
    na_color = [0.88, 0.88, 0.88, 1.0]

    figs = []
    for bench in _benchmarks(records):
        present = [data[(iq, diq, bench)] for iq in iq_sizes for diq in diq_sizes if (iq, diq, bench) in data]
        vmin, vmax = min(present), max(present)
        # Suppress colour scaling when all values are effectively identical
        meaningful = (vmax - vmin) >= COLOR_MIN_RANGE

        cell_text, cell_colors = [], []
        for diq in diq_sizes:
            row_text, row_color = [], []
            for iq in iq_sizes:
                val = data.get((iq, diq, bench))
                if val is None:
                    row_text.append("N/A")
                    row_color.append(na_color)
                else:
                    row_text.append(f"{val:.3f}")
                    norm = (val - vmin) / (vmax - vmin) if meaningful else 0.5
                    row_color.append(list(cmap(norm)))
            cell_text.append(row_text)
            cell_colors.append(row_color)

        n_rows = len(diq_sizes) + 1  # +1 for header
        n_cols = len(iq_sizes)  + 1  # +1 for row labels
        fig, ax = plt.subplots(figsize=(
            max(5, n_cols * 0.70),
            max(2, n_rows * 0.32 + 0.9),
        ))
        ax.axis("off")

        tbl = ax.table(
            cellText=cell_text,
            cellColours=cell_colors,
            rowLabels=[str(d) for d in diq_sizes],
            colLabels=[str(iq) for iq in iq_sizes],
            bbox=[0, 0, 1, 1],
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(9)

        ax.text(0.0, 1.0, "DIQ \\ IQ", transform=ax.transAxes, fontsize=8, va="bottom", ha="left", style="italic")

        unique_ctxs = sorted(set(ctx_map.values()))
        ctx_str = "  ".join(unique_ctxs)
        fig.suptitle(
            f"{bench}\n{ctx_str}\nIPC range {vmin:.3f} - {vmax:.3f} ({100 * (vmax - vmin) / vmin:.1f}%)",
            fontsize=11,
        )
        fig.tight_layout(rect=[0, 0, 1, 0.95])
        figs.append((bench, fig))

    return figs

# ---------------------------------------------------------------------------
# Budget table — one figure per benchmark
#
# columns : total IQ+DIQ budget  (8, 16, 32, 64, 96, 128, 160, …)
# rows    : DIQ size within that budget
# cells   : IPC, color-coded RdYlGn per benchmark (N/A where combo absent)
#
# Designed for budget-constrained sweeps where IQ+DIQ = const per curve.
# ---------------------------------------------------------------------------
def plot_bable(records):
    data      = {(r["iq"] + r["diq"], r["diq"], r["benchmark"]): r["ipc"] for r in records}
    ctx_map   = {r["iq"] + r["diq"]: r["ctx"] for r in records}
    budgets   = sorted(set(r["iq"] + r["diq"] for r in records))
    diq_sizes = sorted(set(r["diq"] for r in records))

    cmap     = plt.cm.RdYlGn
    na_color = [0.88, 0.88, 0.88, 1.0]

    figs = []
    for bench in _benchmarks(records):
        present = [data[(b, d, bench)] for b in budgets for d in diq_sizes if (b, d, bench) in data]
        vmin, vmax = min(present), max(present)
        meaningful = (vmax - vmin) >= COLOR_MIN_RANGE

        cell_text, cell_colors = [], []
        for diq in diq_sizes:
            row_text, row_color = [], []
            for budget in budgets:
                val = data.get((budget, diq, bench))
                if val is None:
                    row_text.append("N/A")
                    row_color.append(na_color)
                else:
                    row_text.append(f"{val:.3f}")
                    norm = (val - vmin) / (vmax - vmin) if meaningful else 0.5
                    row_color.append(list(cmap(norm)))
            cell_text.append(row_text)
            cell_colors.append(row_color)

        n_rows = len(diq_sizes) + 1
        n_cols = len(budgets) + 1
        fig, ax = plt.subplots(figsize=(
            max(5, n_cols * 0.70),
            max(2, n_rows * 0.32 + 0.9),
        ))
        ax.axis("off")

        tbl = ax.table(
            cellText=cell_text,
            cellColours=cell_colors,
            rowLabels=[str(d) for d in diq_sizes],
            colLabels=[str(b) for b in budgets],
            bbox=[0, 0, 1, 1],
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(9)

        ax.text(0.0, 1.0, "DIQ \\ Budget", transform=ax.transAxes, fontsize=8, va="bottom", ha="left", style="italic")

        unique_ctxs = sorted(set(ctx_map.values()))
        ctx_str = "  ".join(unique_ctxs)
        fig.suptitle(
            f"{bench}\n{ctx_str}\nIPC range {vmin:.3f} - {vmax:.3f} ({100 * (vmax - vmin) / vmin:.1f}%)",
            fontsize=11,
        )
        fig.tight_layout(rect=[0, 0, 1, 0.95])
        figs.append((bench, fig))

    return figs


# ---------------------------------------------------------------------------
# Downgrade bar chart — one figure, all benchmarks + GeoMean
# ---------------------------------------------------------------------------
def plot_downgrade(records, baseline_iq=None):
    data    = {(r["iq"], r["diq"], r["ctx"], r["benchmark"]): r["ipc"] for r in records}
    configs = sorted(
        set((r["iq"], r["diq"], r["ctx"]) for r in records),
        key=lambda c: (-c[0], c[2]),
    )
    benchmarks = _benchmarks(records)
    all_ctxs   = set(c[2] for c in configs)

    if baseline_iq is None:
        baseline_iq = max(c[0] for c in configs)
    diqs = set(c[1] for c in configs)

    def _geo_ipc(ctx):
        ipcs = [
            v for b in benchmarks
            for d in diqs
            for v in [data.get((baseline_iq, d, ctx, b))]
            if v
        ]
        return np.exp(np.mean(np.log(ipcs))) if ipcs else 0.0

    baseline_ctx = max(
        set(c[2] for c in configs if c[0] == baseline_iq),
        key=_geo_ipc,
    )
    baseline_diq = min(c[1] for c in configs if c[0] == baseline_iq and c[2] == baseline_ctx)

    n_cfg   = len(configs)
    width   = 0.7 / n_cfg   # 0.7 leaves 30% gap between adjacent groups
    x_bench = 1 + np.arange(len(benchmarks))
    x_geo   = np.array([len(benchmarks) + 1])

    palette = list(plt.cm.tab20.colors) + list(plt.cm.tab20b.colors)
    colors  = {cfg: palette[i % len(palette)] for i, cfg in enumerate(configs)}

    fig, ax = plt.subplots(figsize=(max(12, (len(benchmarks) + 1) * 1.6), 6))

    geo_ratios = {cfg: [] for cfg in configs}

    for i, cfg in enumerate(configs):
        iq, diq, ctx = cfg
        offset  = (i - n_cfg / 2 + 0.5) * width
        iq_part = str(iq) if diq == 0 else f"{iq}/{diq}"
        label   = f"IQ={iq_part}"

        values = []
        for bench in benchmarks:
            ipc_base = data.get((baseline_iq, baseline_diq, baseline_ctx, bench))
            ipc_cfg  = data.get((iq, diq, ctx, bench))
            if ipc_base and ipc_cfg:
                ratio = ipc_cfg / ipc_base
                values.append((1 - ratio) * 100)
                geo_ratios[cfg].append(ratio)
            else:
                values.append(float("nan"))

        bars = ax.bar(x_bench + offset, values, width, color=colors[cfg], label=label,
                      edgecolor="black", linewidth=0.3)
        # Label bars that are large enough to read
        for bar, v in zip(bars, values):
            if not np.isnan(v) and (v < 0 or abs(v) >= 2):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    v + (0.5 if v >= 0 else -0.5),
                    f"{v:.1f}%", ha="center",
                    va="bottom" if v >= 0 else "top",
                    fontsize=7.5, rotation=90
                )

        if geo_ratios[cfg]:
            geo = np.exp(np.mean(np.log(geo_ratios[cfg])))
            gval = (1 - geo) * 100
            gbar = ax.bar(x_geo + offset, [gval], width, color=colors[cfg], edgecolor="black", linewidth=0.3)
            if abs(gval) >= 2:
                ax.text(
                    gbar[0].get_x() + gbar[0].get_width() / 2,
                    gval + (0.5 if gval >= 0 else -0.5),
                    f"{gval:.1f}%", ha="center",
                    va="bottom" if gval >= 0 else "top",
                    fontsize=5.5, rotation=90
                )

    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(np.append(x_bench, x_geo))
    ax.set_xticklabels(
        [b for b in benchmarks] + ["GeoMean"],
        rotation=0, ha="center", fontsize=9,
    )
    ax.set_xlim(0.3, len(benchmarks) + 1.7)
    ax.set_ylabel("Relative Downgrade", fontsize=10)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
    ax.grid(axis="y", which="major", linestyle="--", alpha=0.4)

    ctx_str = ", ".join(sorted(all_ctxs))
    if ctx_str:
        ax.set_title(ctx_str, fontsize=9)
    ax.legend(title=f"baseline: IQ={baseline_iq}", fontsize=8, title_fontsize=8, ncol=1, loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Downgrade bar chart — one figure per benchmark + one GeoMean figure
# ---------------------------------------------------------------------------
def plot_downgrade_split(records, baseline_iq=None):
    data       = {(r["iq"], r["diq"], r["ctx"], r["benchmark"]): r["ipc"] for r in records}
    configs    = sorted(
        set((r["iq"], r["diq"], r["ctx"]) for r in records),
        key=lambda c: (-c[0], c[1], c[2]),
    )
    benchmarks = _benchmarks(records)
    all_ctxs   = set(c[2] for c in configs)

    if baseline_iq is None:
        baseline_iq = max(c[0] for c in configs)
    diqs = set(c[1] for c in configs)

    def _geo_ipc(ctx):
        ipcs = [v for b in benchmarks for d in diqs
                for v in [data.get((baseline_iq, d, ctx, b))] if v]
        return np.exp(np.mean(np.log(ipcs))) if ipcs else 0.0

    baseline_ctx = max(
        set(c[2] for c in configs if c[0] == baseline_iq),
        key=_geo_ipc,
    )
    baseline_diq = min(c[1] for c in configs if c[0] == baseline_iq and c[2] == baseline_ctx)

    palette = list(plt.cm.tab20.colors) + list(plt.cm.tab20b.colors)
    colors  = {cfg: palette[i % len(palette)] for i, cfg in enumerate(configs)}

    x     = np.arange(len(configs))
    width = 0.6

    ctx_str = ", ".join(sorted(all_ctxs))

    cfg_labels = []
    for iq, diq, ctx in configs:
        iq_part = str(iq) if diq == 0 else f"{iq}/{diq}"
        cfg_labels.append(iq_part)

    ratios = {}
    for cfg in configs:
        iq, diq, ctx = cfg
        for bench in benchmarks:
            ipc_base = data.get((baseline_iq, baseline_diq, baseline_ctx, bench))
            ipc_cfg  = data.get((iq, diq, ctx, bench))
            if ipc_base and ipc_cfg:
                ratios[(cfg, bench)] = ipc_cfg / ipc_base

    def _make_bar_fig(vals, title):
        fig, ax = plt.subplots(figsize=(max(12, len(configs) * 0.55), 5))
        bar_colors = [colors[cfg] for cfg in configs]
        bars = ax.bar(x, vals, width, color=bar_colors, edgecolor="black", linewidth=0.3)
        for bar, v in zip(bars, vals):
            if not np.isnan(v) and (v < 0 or abs(v) >= 2):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    v + (0.5 if v >= 0 else -0.5),
                    f"{v:.1f}%", ha="center",
                    va="bottom" if v >= 0 else "top",
                    fontsize=7, rotation=90,
                )
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(cfg_labels, rotation=45, ha="right", fontsize=7)
        ax.set_ylabel("IPC Downgrade vs Baseline")
        ax.yaxis.set_major_formatter(mticker.PercentFormatter())
        ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
        ax.grid(axis="y", which="major", linestyle="--", alpha=0.4)
        title_str = f"{title}  (baseline: IQ={baseline_iq})"
        if ctx_str:
            title_str += f"  [{ctx_str}]"
        ax.set_title(title_str)
        fig.tight_layout()
        return fig

    figs = []
    for bench in benchmarks:
        vals = [(1 - ratios.get((cfg, bench), float("nan"))) * 100 for cfg in configs]
        figs.append((bench, _make_bar_fig(vals, bench)))

    geo_vals = []
    for cfg in configs:
        cfg_rs = [ratios[(cfg, b)] for b in benchmarks if (cfg, b) in ratios]
        geo_vals.append((1 - np.exp(np.mean(np.log(cfg_rs)))) * 100 if cfg_rs else float("nan"))
    figs.append(("geomean", _make_bar_fig(geo_vals, "GeoMean")))

    return figs


# ---------------------------------------------------------------------------
# Per-budget downgrade chart — one figure per IQ+DIQ storage budget
#
# x-axis  : benchmarks + a trailing GeoMean group (grouped bars)
# bars    : one per IQ/DIQ split within that budget, colored per split
# y-axis  : IPC downgrade vs the IQ=budget/DIQ=0 baseline of THAT budget
#
# Answers the iso-budget question: for a fixed total IQ+DIQ budget B, how much
# IPC is lost by carving out DIQ entries vs spending it all on a plain IQ?
# The per-figure baseline is IQ=B/DIQ=0; the y=0 line is that baseline, so the
# baseline's own (always-zero) bar is omitted.
#
# as_ratio=True flips the view to normalized IPC: bars are ipc_cfg/ipc_base and
# the y-axis top is pinned at 1.0 (= identical performance to the baseline),
# with the bottom zoomed to the data so the shortfall below 1.0 is readable.
# ---------------------------------------------------------------------------
def plot_budget_downgrade(records, as_ratio=False):
    data       = {(r["iq"], r["diq"], r["ctx"], r["benchmark"]): r["ipc"] for r in records}
    configs    = sorted(set((r["iq"], r["diq"], r["ctx"]) for r in records))
    benchmarks = _benchmarks(records)

    budget_map = {}
    for cfg in configs:
        iq, diq, _ = cfg
        budget_map.setdefault(iq + diq, []).append(cfg)

    figs = []
    for budget in sorted(budget_map):
        cfgs = budget_map[budget]
        base_cfgs  = [c for c in cfgs if c[1] == 0 and c[0] == budget]
        split_cfgs = sorted((c for c in cfgs if c[1] > 0), key=lambda c: c[1])
        if not base_cfgs or not split_cfgs:
            continue  # need both a baseline and at least one split

        def _geo_ipc(ctx):
            ipcs = [v for b in benchmarks
                    for v in [data.get((budget, 0, ctx, b))] if v]
            return np.exp(np.mean(np.log(ipcs))) if ipcs else 0.0

        baseline_ctx = max(set(c[2] for c in base_cfgs), key=_geo_ipc)

        n_cfg   = len(split_cfgs)
        width   = 0.7 / n_cfg   # 0.7 leaves 30% gap between adjacent groups
        x_bench = 1 + np.arange(len(benchmarks))
        x_geo   = np.array([len(benchmarks) + 1])

        # Sequential colormap: splits are ordered by DIQ/PIQ size, so a viridis
        # gradient encodes the split magnitude (dark = small DIQ → bright = large).
        cmap   = plt.cm.viridis
        fracs  = np.linspace(0, 0.92, n_cfg) if n_cfg > 1 else np.array([0.5])
        colors = {cfg: cmap(f) for cfg, f in zip(split_cfgs, fracs)}

        fig, ax = plt.subplots(figsize=(max(9, (len(benchmarks) + 1) * 1.0), 6))

        plotted = []     # finite plotted values, used to zoom the ratio y-axis
        for i, cfg in enumerate(split_cfgs):
            iq, diq, ctx = cfg
            offset = (i - n_cfg / 2 + 0.5) * width

            values, geo_ratios = [], []
            for bench in benchmarks:
                ipc_base = data.get((budget, 0, baseline_ctx, bench))
                ipc_cfg  = data.get((iq, diq, ctx, bench))
                if ipc_base and ipc_cfg:
                    ratio = ipc_cfg / ipc_base
                    values.append(ratio if as_ratio else (1 - ratio) * 100)
                    geo_ratios.append(ratio)
                else:
                    values.append(float("nan"))
            plotted.extend(v for v in values if not np.isnan(v))

            if geo_ratios:
                geo  = np.exp(np.mean(np.log(geo_ratios)))
                gval = geo if as_ratio else (1 - geo) * 100
            else:
                geo = gval = None

            # The GeoMean bars are too thin to label on-plot legibly, so in the
            # ratio view the per-config GeoMean is carried in the legend label.
            if as_ratio and geo is not None:
                label = f"{iq}/{diq}  (gm {geo:.3f})"
            else:
                label = f"{iq}/{diq}"

            bars = ax.bar(x_bench + offset, values, width, color=colors[cfg], label=label,
                          edgecolor="black", linewidth=0.3)
            for bar, v in zip(bars, values):
                # ratio view: per-benchmark numbers omitted
                if np.isnan(v) or as_ratio:
                    continue
                if v < 0 or abs(v) >= 2:
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        v + (0.5 if v >= 0 else -0.5),
                        f"{v:.1f}%", ha="center",
                        va="bottom" if v >= 0 else "top",
                        fontsize=7.5, rotation=90,
                    )

            if gval is not None:
                plotted.append(gval)
                gbar = ax.bar(x_geo + offset, [gval], width, color=colors[cfg],
                              edgecolor="black", linewidth=0.3)
                if not as_ratio and abs(gval) >= 2:
                    ax.text(
                        gbar[0].get_x() + gbar[0].get_width() / 2,
                        gval + (0.5 if gval >= 0 else -0.5),
                        f"{gval:.1f}%", ha="center",
                        va="bottom" if gval >= 0 else "top",
                        fontsize=5.5, rotation=90,
                    )

        ax.axhline(1.0 if as_ratio else 0.0, color="black", linewidth=0.8)
        ax.set_xticks(np.append(x_bench, x_geo))
        ax.set_xticklabels(
            [b for b in benchmarks] + ["GeoMean"],
            rotation=0, ha="center", fontsize=9,
        )
        ax.set_xlim(0.3, len(benchmarks) + 1.7)
        if as_ratio:
            ax.set_ylabel(f"Performance normalized to baseline (IQ/PIQ={budget}/0)", fontsize=10)
            hi = max(plotted + [1.0])  # expand top so bars that beat the baseline (>1) show
            # Bars MUST start at 0: bar length encodes the value, so a non-zero
            # floor would clip deep-drop splits (e.g. roms_s ~0.26 at B=160) into a
            # tiny sliver and make them read far lower than they are.
            ax.set_ylim(0.0, hi + 0.04)
        else:
            ax.set_ylabel(f"IPC Downgrade vs IQ/PIQ={budget}/0", fontsize=10)
            ax.yaxis.set_major_formatter(mticker.PercentFormatter())
        ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
        ax.grid(axis="y", which="major", linestyle="--", alpha=0.4)

        # Horizontal legend strip across the top, above the title, so no
        # right-hand margin is reserved. With many splits (large budgets) the
        # strip wraps onto two rows so the larger label font still fits within
        # the figure width — saving with bbox_inches="tight" would otherwise
        # widen the PDF to fit a single oversized row.
        leg_title = "IQ/PIQ split  (gm = GeoMean)" if as_ratio else "IQ/PIQ split"
        n_rows = 2 if n_cfg > 8 else 1
        ncol   = -(-n_cfg // n_rows)   # ceil division → balanced rows
        ax.legend(title=leg_title, ncol=ncol,
                  fontsize=13, title_fontsize=11, frameon=False,
                  loc="lower center", bbox_to_anchor=(0.5, 1.0),
                  columnspacing=1.2, handletextpad=0.4, borderaxespad=0.2)
        if not as_ratio:  # ratio plots are shown without a title
            title = f"Budget {budget}  (baseline IQ/PIQ={budget}/0)"
            if baseline_ctx:
                title += f"  [{baseline_ctx}]"
            fig.suptitle(title, fontsize=9, y=0.995)
        fig.tight_layout(rect=[0, 0, 1, 0.83 if n_rows == 2 else 0.90])
        figs.append((f"budget{budget}", fig))

    return figs


# ---------------------------------------------------------------------------
# Shared data prep for the line charts — per-budget IPC normalized to the
# (IQ=B, PIQ=0) baseline of that budget, for both each benchmark and the GeoMean.
# ---------------------------------------------------------------------------
def _budget_lines_data(records):
    """Return (benchmarks, by_budget) where by_budget maps
    budget -> {
        'ctx'         : baseline context string,
        'points'      : [(iq, diq, frac, geo), ...] sorted by diq, incl. baseline
                        (frac = diq/budget; geo = GeoMean IPC ratio, None if absent),
        'bench_ratios': {bench: [(diq, ratio), ...] sorted by diq},
    }.
    Budgets lacking a PIQ=0 baseline or with <2 configs are omitted.  Configs are
    restricted to the baseline's own context so the comparison is iso-context.
    """
    data       = {(r["iq"], r["diq"], r["ctx"], r["benchmark"]): r["ipc"] for r in records}
    configs    = sorted(set((r["iq"], r["diq"], r["ctx"]) for r in records))
    benchmarks = _benchmarks(records)

    budget_map = {}
    for iq, diq, ctx in configs:
        budget_map.setdefault(iq + diq, []).append((iq, diq, ctx))

    by_budget = {}
    for budget in sorted(budget_map):
        base_cfgs = [c for c in budget_map[budget] if c[1] == 0 and c[0] == budget]
        if not base_cfgs:
            continue

        def _geo_ipc(ctx):
            ipcs = [v for b in benchmarks for v in [data.get((budget, 0, ctx, b))] if v]
            return np.exp(np.mean(np.log(ipcs))) if ipcs else 0.0

        baseline_ctx = max(set(c[2] for c in base_cfgs), key=_geo_ipc)
        cfgs = sorted((c for c in budget_map[budget] if c[2] == baseline_ctx),
                      key=lambda c: c[1])
        if len(cfgs) < 2:
            continue

        points = []
        bench_ratios = {b: [] for b in benchmarks}
        for iq, diq, ctx in cfgs:
            ratios = []
            for b in benchmarks:
                ipc_base = data.get((budget, 0, baseline_ctx, b))
                ipc_cfg  = data.get((iq, diq, ctx, b))
                if ipc_base and ipc_cfg:
                    r = ipc_cfg / ipc_base
                    ratios.append(r)
                    bench_ratios[b].append((diq, r))
            geo = np.exp(np.mean(np.log(ratios))) if ratios else None
            points.append((iq, diq, diq / budget, geo))

        by_budget[budget] = {"ctx": baseline_ctx, "points": points,
                             "bench_ratios": bench_ratios}
    return benchmarks, by_budget


def _print_budget_geomeans(budget, baseline_ctx, points, threshold=0.99):
    """Print the GeoMean IPC ratio at each split and the 'knee' — the largest PIQ
    fraction (contiguous from 0) whose GeoMean stays within (1-threshold) of 1.0."""
    ctx_tag = f"  [{baseline_ctx}]" if baseline_ctx else ""
    print(f"Budget {budget} (baseline IQ/PIQ={budget}/0){ctx_tag}:")
    knee, contiguous = None, True   # knee = largest split (diq>0) still within threshold
    for iq, diq, frac, geo in points:
        if geo is None:
            print(f"  PIQ={diq:4d}  IQ={iq:4d}  frac={frac:5.3f}  geomean=   n/a")
            contiguous = False      # a gap breaks the contiguous-from-0 run
            continue
        print(f"  PIQ={diq:4d}  IQ={iq:4d}  frac={frac:5.3f}  geomean={geo:6.4f}")
        if geo < threshold:
            contiguous = False
        elif contiguous and diq > 0:  # baseline (diq=0) is trivially within threshold
            knee = (iq, diq, frac, geo)
    pct = 100 * (1 - threshold)
    if knee:
        print(f"  knee (largest split within {pct:.0f}% of baseline): "
              f"PIQ={knee[1]} (IQ/PIQ={knee[0]}/{knee[1]}, frac={knee[2]:.3f}, geomean={knee[3]:.4f})")
    else:
        print(f"  knee: no split stays within {pct:.0f}% of baseline (even the smallest exceeds it)")
    print()


# ---------------------------------------------------------------------------
# Plot A — multi-budget GeoMean overlay (one figure)
#
# x-axis : PIQ fraction = PIQ / budget (comparable across budgets), incl. 0
# y-axis : GeoMean IPC normalized to each budget's (IQ=B, PIQ=0) baseline
# lines  : one bold viridis line per budget, markers at data points
# ---------------------------------------------------------------------------
def plot_geomean_lines(records):
    _, by_budget = _budget_lines_data(records)
    budgets = sorted(by_budget)

    print("\n=== GeoMean normalized IPC per split (all budgets) ===")
    for B in budgets:
        _print_budget_geomeans(B, by_budget[B]["ctx"], by_budget[B]["points"])

    cmap   = plt.cm.viridis
    fracs  = np.linspace(0, 0.85, len(budgets)) if len(budgets) > 1 else np.array([0.5])
    colors = {B: cmap(f) for B, f in zip(budgets, fracs)}

    fig, ax = plt.subplots(figsize=(7, 4.5))
    max_frac, lo, hi = 0.0, 1.0, 1.0
    for B in budgets:
        pts = [(frac, geo) for (_, _, frac, geo) in by_budget[B]["points"] if geo is not None]
        if not pts:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        max_frac = max(max_frac, max(xs))
        lo, hi = min(lo, min(ys)), max(hi, max(ys))
        ax.plot(xs, ys, marker="o", markersize=5, linewidth=2.2,
                color=colors[B], label=f"B={B}")

    ax.axhline(1.0, color="black", linewidth=0.9, linestyle="--")
    ax.set_xlabel("PIQ fraction  (PIQ / budget)", fontsize=11)
    ax.set_ylabel("GeoMean IPC normalized to baseline (PIQ=0)", fontsize=11)
    ax.set_xlim(-0.01, max_frac + 0.03)
    ax.set_ylim(max(0.0, lo - 0.05), hi + 0.02)  # no bottom truncation
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.legend(title="Budget", fontsize=9, title_fontsize=9, ncol=2)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Plot B — per-budget detail (one figure per budget)
#
# x-axis : PIQ entries in the split (0, 10, 20, …), baseline at 0
# y-axis : IPC normalized to (IQ=B, PIQ=0)
# lines  : thin light-grey line per benchmark (no legend) + bold GeoMean line
# ---------------------------------------------------------------------------
# IPC-preserving split per budget: the PIQ (DIQ) entry count at which the
# GeoMean IPC matches the IQ=B/0 baseline.  Marked with a diamond on the
# GeoMean line.  Keyed by budget B; budget 16 has none.
IPC_PRESERVING_PIQ = {32: 10, 64: 20, 96: 40, 128: 70, 160: 100}


def plot_budget_lines(records):
    benchmarks, by_budget = _budget_lines_data(records)

    # Shared vertical scale across every budget figure so they are directly
    # comparable side by side.  Gather all plotted ratios (per-benchmark +
    # GeoMean, plus the 1.0 baseline) up front and derive one common y-range.
    all_global = [1.0]
    for info in by_budget.values():
        for series in info["bench_ratios"].values():
            all_global.extend(r for _, r in series)
        all_global.extend(geo for (_, _, _, geo) in info["points"] if geo is not None)
    y_lo = max(0.0, min(all_global) - 0.05)  # no bottom truncation
    y_hi = max(all_global) + 0.03

    figs = []
    for B in sorted(by_budget):
        info = by_budget[B]
        _print_budget_geomeans(B, info["ctx"], info["points"])

        fig, ax = plt.subplots(figsize=(7, 4.5))

        # One coloured line per benchmark.  The default colour cycle only has ~10
        # colours, so with ~20 benchmarks they wrap; switch solid -> dashed once we
        # wrap so every (colour, style) pair is unique (mirrors plot_dep.py
        # make_cumul_all).  The GeoMean below stays bold on top.
        n_colors = len(plt.rcParams["axes.prop_cycle"])
        for i, b in enumerate(benchmarks):
            series = sorted(info["bench_ratios"][b], key=lambda t: t[0])
            if not series:
                continue
            xs = [d for d, _ in series]
            ys = [r for _, r in series]
            linestyle = "-" if (i // n_colors) % 2 == 0 else "--"
            ax.plot(xs, ys, linewidth=1.1, linestyle=linestyle, alpha=0.9,
                    zorder=1, label=b)

        gpts = [(diq, geo) for (_, diq, _, geo) in info["points"] if geo is not None]
        gx = [d for d, _ in gpts]
        gy = [g for _, g in gpts]
        ax.plot(gx, gy, color="black", linewidth=2.8,
                marker="o", markersize=5, zorder=3, label="GeoMean")

        # Mark the IPC-preserving split (largest PIQ that still matches the
        # IQ=B/0 baseline) with a diamond on the GeoMean line.
        piq_keep = IPC_PRESERVING_PIQ.get(B)
        if piq_keep is not None:
            keep = [(diq, g) for diq, g in zip(gx, gy) if diq == piq_keep]
            if keep:
                kx, ky = keep[0]
                ax.plot([kx], [ky], marker="D", markersize=7, color="black",
                        markerfacecolor="gold", markeredgewidth=1.3,
                        linestyle="none", zorder=4,
                        label="IPC-preserving split")

        ax.axhline(1.0, color="black", linewidth=0.9, linestyle="--")
        ax.set_xlabel("PIQ entries in split", fontsize=11)
        ax.set_ylabel(f"IPC normalized to baseline (IQ/PIQ={B}/0)", fontsize=11)
        ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))  # PIQ entries are integers
        ax.set_ylim(y_lo, y_hi)  # shared across all budget figures
        ax.grid(True, linestyle="--", alpha=0.35)
        ax.legend(fontsize=7, ncol=2)
        fig.tight_layout()
        figs.append((f"budget{B}", fig))

    return figs


# ---------------------------------------------------------------------------
# Budget-grouped bar chart — one figure per benchmark + GeoMean
#
# x-axis  : total IQ+DIQ budget, grouped into decade buckets (40s, 50s, …)
# bars    : one bar per config in that bucket, colored by base IQ size
#           ordered largest→smallest base IQ left→right within each group
# y-axis  : same IPC downgrade % as --split / --downgrade
#
# This answers: "for the same total IQ budget, does a different split help?"
# ---------------------------------------------------------------------------
def plot_budget_groups(records, baseline_iq=None):
    data       = {(r["iq"], r["diq"], r["ctx"], r["benchmark"]): r["ipc"] for r in records}
    configs    = sorted(set((r["iq"], r["diq"], r["ctx"]) for r in records))
    benchmarks = _benchmarks(records)
    all_ctxs   = set(c[2] for c in configs)

    if baseline_iq is None:
        baseline_iq = max(c[0] for c in configs)
    diqs = set(c[1] for c in configs)

    def _geo_ipc(ctx):
        ipcs = [v for b in benchmarks for d in diqs
                for v in [data.get((baseline_iq, d, ctx, b))] if v]
        return np.exp(np.mean(np.log(ipcs))) if ipcs else 0.0

    baseline_ctx = max(set(c[2] for c in configs if c[0] == baseline_iq), key=_geo_ipc)
    baseline_diq = min(c[1] for c in configs if c[0] == baseline_iq and c[2] == baseline_ctx)

    bucket_map = {}
    for cfg in configs:
        iq, diq, _ = cfg
        bucket = iq + diq  # exact budget value
        bucket_map.setdefault(bucket, []).append(cfg)
    sorted_buckets = sorted(bucket_map)
    for b in sorted_buckets:
        bucket_map[b].sort(key=lambda c: (-c[0], c[1]))  # largest base IQ leftmost

    # Color by DIQ size so the split size is immediately visible in the legend
    diq_vals   = sorted(set(c[1] for c in configs))
    palette    = list(plt.cm.tab20.colors) + list(plt.cm.tab20b.colors)
    diq_colors = {diq: palette[i] for i, diq in enumerate(diq_vals)}

    ratios = {}
    for cfg in configs:
        iq, diq, ctx = cfg
        for bench in benchmarks:
            ipc_base = data.get((baseline_iq, baseline_diq, baseline_ctx, bench))
            ipc_cfg  = data.get((iq, diq, ctx, bench))
            if ipc_base and ipc_cfg:
                ratios[(cfg, bench)] = ipc_cfg / ipc_base

    ctx_str = ", ".join(sorted(all_ctxs))

    bar_w  = 0.8
    gap    = 0.6
    x_pos  = {}
    tick_x = {}
    cur    = 0.0
    for bucket in sorted_buckets:
        cfgs = bucket_map[bucket]
        positions = [cur + i * bar_w for i in range(len(cfgs))]
        tick_x[bucket] = sum(positions) / len(positions)
        for cfg, px in zip(cfgs, positions):
            x_pos[cfg] = px
        cur += len(cfgs) * bar_w + gap

    fig_w = max(12, cur * 0.6)

    def _make_fig(vals_by_cfg, title):
        fig, ax = plt.subplots(figsize=(fig_w, 5))
        for cfg in configs:
            _, diq, _ = cfg
            v = vals_by_cfg.get(cfg, float("nan"))
            ax.bar(x_pos[cfg], v, bar_w * 0.9,
                   color=diq_colors[diq], edgecolor="black", linewidth=0.3)
            if not np.isnan(v) and (v < 0 or abs(v) >= 2):
                ax.text(x_pos[cfg] + bar_w * 0.45,
                        v + (0.4 if v >= 0 else -0.4),
                        f"{v:.1f}%", ha="center",
                        va="bottom" if v >= 0 else "top",
                        fontsize=6, rotation=90)
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_xticks(list(tick_x.values()))
        ax.set_xticklabels([str(b) for b in sorted_buckets], rotation=0, ha="center", fontsize=8)
        ax.set_xlabel("IQ + DIQ budget  (largest→smallest base IQ, i.e. smallest→largest DIQ, left→right within group)")
        ax.set_ylabel("IPC Downgrade vs Baseline")
        ax.yaxis.set_major_formatter(mticker.PercentFormatter())
        ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
        ax.grid(axis="y", which="major", linestyle="--", alpha=0.4)
        title_str = f"{title}  (baseline: IQ={baseline_iq})"
        if ctx_str:
            title_str += f"  [{ctx_str}]"
        ax.set_title(title_str)
        # Only legend entries for DIQ values that actually appear in this data
        present_diqs = sorted(set(c[1] for c in configs))
        patches = [mpatches.Patch(facecolor=diq_colors[diq], edgecolor="black", label=f"DIQ={diq}")
                   for diq in present_diqs]
        ax.legend(handles=patches, title="DIQ size", fontsize=7, title_fontsize=8, ncol=2)
        fig.tight_layout()
        return fig

    figs = []
    for bench in benchmarks:
        vals = {cfg: (1 - ratios.get((cfg, bench), float("nan"))) * 100 for cfg in configs}
        figs.append((bench, _make_fig(vals, bench)))

    geo_vals = {}
    for cfg in configs:
        rs = [ratios[(cfg, b)] for b in benchmarks if (cfg, b) in ratios]
        geo_vals[cfg] = (1 - np.exp(np.mean(np.log(rs)))) * 100 if rs else float("nan")
    figs.append(("geomean", _make_fig(geo_vals, "GeoMean")))

    return figs


# ---------------------------------------------------------------------------
# IQ-grouped bar chart — one figure per benchmark + GeoMean
#
# x-axis  : DIQ sizes, grouped by base IQ (all IQ=32 configs, then IQ=64, …)
#           DIQ ascending left→right within each group
# bars    : colored by base IQ (same tab10 palette as --budget)
# y-axis  : same IPC downgrade % as --split / --downgrade
# group labels printed on a twin top-axis (IQ=32, IQ=64, …)
#
# This answers: "for a fixed base IQ, how does adding more DIQ help?"
# ---------------------------------------------------------------------------
def plot_iq_groups(records, baseline_iq=None):
    data       = {(r["iq"], r["diq"], r["ctx"], r["benchmark"]): r["ipc"] for r in records}
    configs    = sorted(set((r["iq"], r["diq"], r["ctx"]) for r in records))
    benchmarks = _benchmarks(records)
    all_ctxs   = set(c[2] for c in configs)

    if baseline_iq is None:
        baseline_iq = max(c[0] for c in configs)
    diqs = set(c[1] for c in configs)

    def _geo_ipc(ctx):
        ipcs = [v for b in benchmarks for d in diqs
                for v in [data.get((baseline_iq, d, ctx, b))] if v]
        return np.exp(np.mean(np.log(ipcs))) if ipcs else 0.0

    baseline_ctx = max(set(c[2] for c in configs if c[0] == baseline_iq), key=_geo_ipc)
    baseline_diq = min(c[1] for c in configs if c[0] == baseline_iq and c[2] == baseline_ctx)

    iq_groups = {}
    for cfg in configs:
        iq_groups.setdefault(cfg[0], []).append(cfg)
    iq_sizes = sorted(iq_groups.keys())
    for iq in iq_sizes:
        iq_groups[iq].sort(key=lambda c: c[1])  # ascending DIQ

    iq_colors = {iq: plt.cm.tab10.colors[i] for i, iq in enumerate(iq_sizes)}

    ratios = {}
    for cfg in configs:
        iq, diq, ctx = cfg
        for bench in benchmarks:
            ipc_base = data.get((baseline_iq, baseline_diq, baseline_ctx, bench))
            ipc_cfg  = data.get((iq, diq, ctx, bench))
            if ipc_base and ipc_cfg:
                ratios[(cfg, bench)] = ipc_cfg / ipc_base

    ctx_str = ", ".join(sorted(all_ctxs))

    bar_w      = 0.8
    gap        = 1.2   # wider gap between IQ groups than within
    x_pos      = {}
    group_info = {}    # iq -> (center_x, last_bar_x)
    cur        = 0.0
    for iq in iq_sizes:
        cfgs      = iq_groups[iq]
        positions = [cur + i * bar_w for i in range(len(cfgs))]
        group_info[iq] = (sum(positions) / len(positions), positions[-1])
        for cfg, px in zip(cfgs, positions):
            x_pos[cfg] = px
        cur += len(cfgs) * bar_w + gap

    fig_w  = max(12, cur * 0.55)
    x_lo   = -gap / 2
    x_hi   = cur - gap / 2

    def _make_fig(vals_by_cfg, title):
        fig, ax = plt.subplots(figsize=(fig_w, 5.5))

        bar_xs, bar_labels = [], []
        for iq in iq_sizes:
            for cfg in iq_groups[iq]:
                v = vals_by_cfg.get(cfg, float("nan"))
                ax.bar(x_pos[cfg], v, bar_w * 0.9,
                       color=iq_colors[iq], edgecolor="black", linewidth=0.3)
                if not np.isnan(v) and (v < 0 or abs(v) >= 2):
                    ax.text(x_pos[cfg] + bar_w * 0.45,
                            v + (0.4 if v >= 0 else -0.4),
                            f"{v:.1f}%", ha="center",
                            va="bottom" if v >= 0 else "top",
                            fontsize=6, rotation=90)
                bar_xs.append(x_pos[cfg])
                bar_labels.append(str(cfg[1]))  # DIQ value

        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_xlim(x_lo, x_hi)

        # Vertical separators between IQ groups
        for i, iq in enumerate(iq_sizes[:-1]):
            _, last_x = group_info[iq]
            next_x    = x_pos[iq_groups[iq_sizes[i + 1]][0]]
            ax.axvline((last_x + next_x) / 2, color="gray",
                       linewidth=1.0, linestyle="--", alpha=0.5)

        # IQ group labels on a twin top-axis
        ax2 = ax.twiny()
        ax2.set_xlim(x_lo, x_hi)
        ax2.set_xticks([group_info[iq][0] for iq in iq_sizes])
        ax2.set_xticklabels([f"IQ={iq}" for iq in iq_sizes],
                            fontsize=9, fontweight="bold")
        ax2.tick_params(length=0)

        ax.set_xticks(bar_xs)
        ax.set_xticklabels(bar_labels, rotation=0, ha="center", fontsize=7)
        ax.set_xlabel("DIQ size")
        ax.set_ylabel("IPC Downgrade vs Baseline")
        ax.yaxis.set_major_formatter(mticker.PercentFormatter())
        ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
        ax.grid(axis="y", which="major", linestyle="--", alpha=0.4)
        title_str = f"{title}  (baseline: IQ={baseline_iq})"
        if ctx_str:
            title_str += f"  [{ctx_str}]"
        ax.set_title(title_str, pad=12)
        patches = [mpatches.Patch(facecolor=iq_colors[iq], edgecolor="black", label=f"IQ={iq}")
                   for iq in iq_sizes]
        ax.legend(handles=patches, fontsize=8)
        fig.tight_layout()
        return fig

    figs = []
    for bench in benchmarks:
        vals = {cfg: (1 - ratios.get((cfg, bench), float("nan"))) * 100 for cfg in configs}
        figs.append((bench, _make_fig(vals, bench)))

    geo_vals = {}
    for cfg in configs:
        rs = [ratios[(cfg, b)] for b in benchmarks if (cfg, b) in ratios]
        geo_vals[cfg] = (1 - np.exp(np.mean(np.log(rs)))) * 100 if rs else float("nan")
    figs.append(("geomean", _make_fig(geo_vals, "GeoMean")))

    return figs


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", dest="results_file", type=str, default=str(RESULTS_FILE), help="Path to results txt file")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--bar",       dest="mode", action="store_const", const="bar",       help="Grouped bar chart (good for small config sets)")
    mode.add_argument("--table",     dest="mode", action="store_const", const="table",     help="Heatmap table: rows = DIQ, columns = IQ")
    mode.add_argument("--bable",     dest="mode", action="store_const", const="bable",     help="Budget table: rows = DIQ size, columns = total IQ+DIQ budget")
    mode.add_argument("--downgrade", dest="mode", action="store_const", const="downgrade", help="Relative IPC downgrade vs baseline IQ, all benchmarks in one figure")
    mode.add_argument("--split",     dest="mode", action="store_const", const="split",     help="Like --downgrade but one figure per benchmark + GeoMean (5 figures total)")
    mode.add_argument("--budget",    dest="mode", action="store_const", const="budget",    help="Per-benchmark figures grouped by total IQ+DIQ budget decade, bars colored by base IQ")
    mode.add_argument("--budget-downgrade", dest="mode", action="store_const", const="budget-downgrade", help="One figure per IQ+DIQ budget; x=benchmarks+GeoMean, bars=IQ/DIQ splits, baseline=IQ=budget/DIQ=0")
    mode.add_argument("--budget-ratio", dest="mode", action="store_const", const="budget-ratio", help="Like --budget-downgrade but y-axis = normalized IPC with top pinned at 1.0 (baseline = identical performance)")
    mode.add_argument("--geomean-lines", dest="mode", action="store_const", const="geomean-lines", help="One figure: GeoMean IPC (normalized per budget) vs PIQ fraction, one line per budget")
    mode.add_argument("--budget-lines", dest="mode", action="store_const", const="budget-lines", help="One figure per budget: per-benchmark + GeoMean normalized IPC vs PIQ entries")
    mode.add_argument("--iq-groups", dest="mode", action="store_const", const="iq-groups", help="Per-benchmark figures grouped by base IQ size, x-axis = DIQ values")
    parser.add_argument("--baseline", dest="baseline", type=str, default="160/0", help="Baseline config for bar chart normalisation (default: 160/0)")
    parser.add_argument("--baseline-iq", dest="baseline_iq", type=int, default=None, help="Baseline IQ size for --downgrade / --split / --budget / --iq-groups (default: largest IQ in data)")
    parser.add_argument("-s", dest="save", action="store_true", help="Save each figure to plot_ipc/<mode>_<bench>.pdf")
    args = parser.parse_args()

    records = parse_results(Path(args.results_file))
    write_csv(records, CSV_OUT)
    print(f"Wrote {CSV_OUT}")

    ctx = _file_ctx(records)

    try:
        if args.mode == "downgrade":
            fig = plot_downgrade(records, baseline_iq=args.baseline_iq)
            if args.save:
                out = PLOT_DIR / f"downgrade_{ctx}.pdf"
                fig.savefig(out, dpi=150)
                print(f"Saved {out}")
            plt.show()
            sys.exit(0)
        elif args.mode == "split":
            figs = plot_downgrade_split(records, baseline_iq=args.baseline_iq)
            for name, fig in figs:
                if args.save:
                    out = PLOT_DIR / f"downgrade_{name}_{ctx}.pdf"
                    fig.savefig(out, dpi=150)
                    print(f"Saved {out}")
            plt.show()
            sys.exit(0)
        elif args.mode == "budget":
            figs = plot_budget_groups(records, baseline_iq=args.baseline_iq)
            for name, fig in figs:
                if args.save:
                    out = PLOT_DIR / f"budget_{name}_{ctx}.pdf"
                    fig.savefig(out, dpi=150)
                    print(f"Saved {out}")
            plt.show()
            sys.exit(0)
        elif args.mode in ("budget-downgrade", "budget-ratio"):
            as_ratio = args.mode == "budget-ratio"
            figs = plot_budget_downgrade(records, as_ratio=as_ratio)
            tag  = "budget_ratio" if as_ratio else "budget_downgrade"
            for name, fig in figs:
                if args.save:
                    out = PLOT_DIR / f"{tag}_{name}_{ctx}.pdf"
                    fig.savefig(out, dpi=150, bbox_inches="tight")
                    print(f"Saved {out}")
            plt.show()
            sys.exit(0)
        elif args.mode == "geomean-lines":
            fig = plot_geomean_lines(records)
            if args.save:
                out = PLOT_DIR / f"geomean_lines_allbudgets_{ctx}.pdf"
                fig.savefig(out, dpi=300, bbox_inches="tight")
                print(f"Saved {out}")
            plt.show()
            sys.exit(0)
        elif args.mode == "budget-lines":
            figs = plot_budget_lines(records)
            for name, fig in figs:
                if args.save:
                    out = PLOT_DIR / f"budget_lines_{name}_{ctx}.pdf"
                    fig.savefig(out, dpi=300, bbox_inches="tight")
                    print(f"Saved {out}")
            plt.show()
            sys.exit(0)
        elif args.mode == "iq-groups":
            figs = plot_iq_groups(records, baseline_iq=args.baseline_iq)
            for name, fig in figs:
                if args.save:
                    out = PLOT_DIR / f"iq_groups_{name}_{ctx}.pdf"
                    fig.savefig(out, dpi=150)
                    print(f"Saved {out}")
            plt.show()
            sys.exit(0)
        elif args.mode == "bar":
            figs = plot_bars(records, baseline_cfg=args.baseline)
            mode_tag = "bar"
        elif args.mode == "table":
            figs = plot_table(records)
            mode_tag = "table"
        elif args.mode == "bable":
            figs = plot_bable(records)
            mode_tag = "bable"
        else:
            figs = plot_lines(records)
            mode_tag = "lines"

        for bench, fig in figs:
            if args.save:
                out = PLOT_DIR / f"{mode_tag}_{bench}_{ctx}.pdf"
                fig.savefig(out, dpi=150)
                print(f"Saved {out}")

        # plt.show()
    except KeyboardInterrupt:
        sys.exit(0)
