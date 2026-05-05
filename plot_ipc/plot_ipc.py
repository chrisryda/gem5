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

BENCHMARK_ORDER = ["whetstone", "mcf_s", "gcc_s", "lbm_s"]
BENCH_LABELS    = {"whetstone": "Whetstone", "mcf_s": "mcf_s",
                   "gcc_s": "gcc_s",         "lbm_s": "lbm_s"}

# Minimum IPC range before colour scaling is considered meaningful.
# Values within this band are treated as identical (mapped to neutral 0.5).
COLOR_MIN_RANGE = 0.01


def _ctx_from_runtag(runtag: str) -> str:
    """Strip the _iqN and _diqN components from a SIM_TAG to get run context."""
    ctx = re.sub(r'_iq\d+', '', runtag)
    ctx = re.sub(r'_diq\d+', '', ctx)
    return ctx


def _iq_label(iq: int, ctx: str) -> str:
    return f"{iq}\n({ctx})" if ctx else str(iq)


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

        ax.set_title(BENCH_LABELS.get(bench, bench))
        ax.set_xlabel("IQ size")
        ax.set_ylabel("IPC")
        ax.set_xticks(iq_sizes)
        ax.set_xticklabels([_iq_label(iq, ctx_map.get(iq, "")) for iq in iq_sizes], fontsize=7)
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
    cfg_labels = [f"{c}\n({ctx_map.get(c, '')})" if ctx_map.get(c) else c for c in configs]
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

        fig.suptitle(BENCH_LABELS.get(bench, bench), fontsize=13)
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

        fig, ax = plt.subplots(figsize=(
            max(8, len(iq_sizes) * 1.4),
            max(4, len(diq_sizes) * 0.6 + 1.5)
        ))
        ax.axis("off")

        tbl = ax.table(
            cellText=cell_text,
            cellColours=cell_colors,
            rowLabels=[str(d) for d in diq_sizes],
            colLabels=[_iq_label(iq, ctx_map.get(iq, "")) for iq in iq_sizes],
            loc="center",
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(9)
        tbl.scale(1.2, 1.6)

        ax.text(0.01, 0.98, "DIQ \\ IQ", transform=ax.transAxes, fontsize=8, va="top", ha="left", style="italic")

        fig.suptitle(
            f"{BENCH_LABELS.get(bench, bench)}  "
            f"(green = high IPC, red = low — range {vmin:.3f}–{vmax:.3f})",
            fontsize=11,
        )
        fig.tight_layout()
        figs.append((bench, fig))

    return figs


# ---------------------------------------------------------------------------
# Downgrade bar chart — one figure, all benchmarks + GeoMean
# ---------------------------------------------------------------------------
def _short_ctx(ctx: str, all_ctxs) -> str:
    """Strip the leading sim-time component (e.g. 't10B_', 'c5M_') shared by all contexts."""
    if not ctx:
        return ""
    common = re.match(r'^[tc]\d+[BM]_?', ctx)
    prefix_len = len(common.group()) if common else 0
    # Only strip if every ctx starts with the same prefix
    if prefix_len and all(c.startswith(ctx[:prefix_len]) for c in all_ctxs if c):
        return ctx[prefix_len:]
    return ctx


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
        short   = _short_ctx(ctx, all_ctxs)
        label   = f"IQ={iq_part} ({short})" if short else f"IQ={iq_part}"

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
        [BENCH_LABELS.get(b, b) for b in benchmarks] + ["GeoMean"],
        rotation=0, ha="center", fontsize=9,
    )
    ax.set_xlim(0.3, len(benchmarks) + 1.7)
    ax.set_ylabel("Relative Downgrade", fontsize=10)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
    ax.grid(axis="y", which="major", linestyle="--", alpha=0.4)

    short_base = _short_ctx(baseline_ctx, all_ctxs)
    base_label = f"IQ={baseline_iq} ({short_base})" if short_base else f"IQ={baseline_iq}"
    ax.legend(title=f"baseline: {base_label}", fontsize=8, title_fontsize=8, ncol=1, loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Downgrade bar chart — one figure per benchmark + one GeoMean figure
# ---------------------------------------------------------------------------
def plot_downgrade_split(records, baseline_iq=None):
    data       = {(r["iq"], r["diq"], r["ctx"], r["benchmark"]): r["ipc"] for r in records}
    configs    = sorted(
        set((r["iq"], r["diq"], r["ctx"]) for r in records),
        key=lambda c: (-c[0], c[2]),
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

    short_base = _short_ctx(baseline_ctx, all_ctxs)
    base_label = f"IQ={baseline_iq} ({short_base})" if short_base else f"IQ={baseline_iq}"

    cfg_labels = []
    for iq, diq, ctx in configs:
        short   = _short_ctx(ctx, all_ctxs)
        iq_part = str(iq) if diq == 0 else f"{iq}/{diq}"
        cfg_labels.append(f"{iq_part}\n({short})" if short else iq_part)

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
        ax.set_title(f"{title}  (baseline: {base_label})")
        fig.tight_layout()
        return fig

    figs = []
    for bench in benchmarks:
        vals = [(1 - ratios.get((cfg, bench), float("nan"))) * 100 for cfg in configs]
        figs.append((bench, _make_bar_fig(vals, BENCH_LABELS.get(bench, bench))))

    geo_vals = []
    for cfg in configs:
        cfg_rs = [ratios[(cfg, b)] for b in benchmarks if (cfg, b) in ratios]
        geo_vals.append((1 - np.exp(np.mean(np.log(cfg_rs)))) * 100 if cfg_rs else float("nan"))
    figs.append(("geomean", _make_bar_fig(geo_vals, "GeoMean")))

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
def plot_budget_groups(records, baseline_iq=None, bucket_size=10):
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
        bucket = ((iq + diq) // bucket_size) * bucket_size
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

    short_base = _short_ctx(baseline_ctx, all_ctxs)
    base_label = f"IQ={baseline_iq} ({short_base})" if short_base else f"IQ={baseline_iq}"

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
        ax.set_xticklabels([f"{b}s" for b in sorted_buckets], rotation=0, ha="center", fontsize=8)
        ax.set_xlabel("IQ + DIQ budget  (largest→smallest base IQ, i.e. smallest→largest DIQ, left→right within group)")
        ax.set_ylabel("IPC Downgrade vs Baseline")
        ax.yaxis.set_major_formatter(mticker.PercentFormatter())
        ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
        ax.grid(axis="y", which="major", linestyle="--", alpha=0.4)
        ax.set_title(f"{title}  (baseline: {base_label})")
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
        figs.append((bench, _make_fig(vals, BENCH_LABELS.get(bench, bench))))

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

    short_base = _short_ctx(baseline_ctx, all_ctxs)
    base_label = f"IQ={baseline_iq} ({short_base})" if short_base else f"IQ={baseline_iq}"

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
        ax.set_title(f"{title}  (baseline: {base_label})", pad=12)
        patches = [mpatches.Patch(facecolor=iq_colors[iq], edgecolor="black", label=f"IQ={iq}")
                   for iq in iq_sizes]
        ax.legend(handles=patches, fontsize=8)
        fig.tight_layout()
        return fig

    figs = []
    for bench in benchmarks:
        vals = {cfg: (1 - ratios.get((cfg, bench), float("nan"))) * 100 for cfg in configs}
        figs.append((bench, _make_fig(vals, BENCH_LABELS.get(bench, bench))))

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
    mode.add_argument("--downgrade", dest="mode", action="store_const", const="downgrade", help="Relative IPC downgrade vs baseline IQ, all benchmarks in one figure")
    mode.add_argument("--split",     dest="mode", action="store_const", const="split",     help="Like --downgrade but one figure per benchmark + GeoMean (5 figures total)")
    mode.add_argument("--budget",    dest="mode", action="store_const", const="budget",    help="Per-benchmark figures grouped by total IQ+DIQ budget decade, bars colored by base IQ")
    mode.add_argument("--iq-groups", dest="mode", action="store_const", const="iq-groups", help="Per-benchmark figures grouped by base IQ size, x-axis = DIQ values")
    parser.add_argument("--baseline", dest="baseline", type=str, default="160/0", help="Baseline config for bar chart normalisation (default: 160/0)")
    parser.add_argument("--baseline-iq", dest="baseline_iq", type=int, default=None, help="Baseline IQ size for --downgrade / --split / --budget / --iq-groups (default: largest IQ in data)")
    parser.add_argument("-s", dest="save", action="store_true", help="Save each figure to plot_ipc/<mode>_<bench>.png")
    args = parser.parse_args()

    records = parse_results(Path(args.results_file))
    write_csv(records, CSV_OUT)
    print(f"Wrote {CSV_OUT}")

    try:
        if args.mode == "downgrade":
            fig = plot_downgrade(records, baseline_iq=args.baseline_iq)
            if args.save:
                out = PLOT_DIR / "downgrade.png"
                fig.savefig(out, dpi=150)
                print(f"Saved {out}")
            plt.show()
            sys.exit(0)
        elif args.mode == "split":
            figs = plot_downgrade_split(records, baseline_iq=args.baseline_iq)
            for name, fig in figs:
                if args.save:
                    out = PLOT_DIR / f"downgrade_{name}.png"
                    fig.savefig(out, dpi=150)
                    print(f"Saved {out}")
            plt.show()
            sys.exit(0)
        elif args.mode == "budget":
            figs = plot_budget_groups(records, baseline_iq=args.baseline_iq)
            for name, fig in figs:
                if args.save:
                    out = PLOT_DIR / f"budget_{name}.png"
                    fig.savefig(out, dpi=150)
                    print(f"Saved {out}")
            plt.show()
            sys.exit(0)
        elif args.mode == "iq-groups":
            figs = plot_iq_groups(records, baseline_iq=args.baseline_iq)
            for name, fig in figs:
                if args.save:
                    out = PLOT_DIR / f"iq_groups_{name}.png"
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
        else:
            figs = plot_lines(records)
            mode_tag = "lines"

        for bench, fig in figs:
            if args.save:
                out = PLOT_DIR / f"{mode_tag}_{bench}.png"
                fig.savefig(out, dpi=150)
                print(f"Saved {out}")

        plt.show()
    except KeyboardInterrupt:
        sys.exit(0)
