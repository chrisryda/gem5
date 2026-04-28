import argparse
import re
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

RESULTS_FILE = Path(__file__).parent.parent / "iq-sweep-results.txt"
CSV_OUT      = Path(__file__).parent / "iq_sweep_ipc.csv"
PLOT_DIR     = Path(__file__).parent

BENCHMARK_ORDER = ["whetstone", "mcf_s", "gcc_s", "lbm_s"]
BENCH_LABELS    = {"whetstone": "Whetstone", "mcf_s": "mcf_s",
                   "gcc_s": "gcc_s",         "lbm_s": "lbm_s"}

# Minimum IPC range before colour scaling is considered meaningful.
# Values within this band are treated as identical (mapped to neutral 0.5).
COLOR_MIN_RANGE = 0.01


def parse_results(path):
    records, current = [], {}
    with open(path) as f:
        for raw in f:
            line = raw.strip()

            m = re.match(r'^(\w+)\s+IQ=(\d+)\s+DIQ=(\d+)\s+SIM_TAG=(\d+/\d+)$', line)
            if m:
                current = {
                    "benchmark": m.group(1),
                    "iq":  int(m.group(2)),
                    "diq": int(m.group(3)),
                    "config": m.group(4),
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
    fields = ["benchmark", "config", "iq", "diq",
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
    data    = {(r["config"], r["benchmark"]): r["ipc"] for r in records}
    configs = sorted(set(r["config"] for r in records),
                     key=lambda c: (int(c.split("/")[0]), int(c.split("/")[1])))
    colors  = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    sep_x   = configs.index(additive_cfg) - 0.5 if additive_cfg in configs else None

    def _sep(ax):
        if sep_x is not None:
            ax.axvline(sep_x, color="gray", linewidth=1.2, linestyle=":")
            ax.text(sep_x + 0.05, ax.get_ylim()[1] * 0.97,
                    "additive →", fontsize=7, color="gray", va="top")

    x      = np.arange(len(configs))
    width  = 0.20

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
        ax.set_xticklabels(configs, rotation=45, ha="right")
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
        ax.set_xticklabels(configs, rotation=45, ha="right")
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
    iq_sizes  = sorted(set(r["iq"]  for r in records))
    diq_sizes = sorted(set(r["diq"] for r in records))

    cmap     = plt.cm.RdYlGn
    na_color = [0.88, 0.88, 0.88, 1.0]

    figs = []
    for bench in _benchmarks(records):
        present = [data[(iq, diq, bench)]
                   for iq in iq_sizes for diq in diq_sizes
                   if (iq, diq, bench) in data]
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

        fig, ax = plt.subplots(figsize=(max(8, len(iq_sizes) * 1.4),
                                        max(4, len(diq_sizes) * 0.6 + 1.5)))
        ax.axis("off")

        tbl = ax.table(
            cellText=cell_text,
            cellColours=cell_colors,
            rowLabels=[str(d) for d in diq_sizes],
            colLabels=[str(iq) for iq in iq_sizes],
            loc="center",
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(9)
        tbl.scale(1.2, 1.6)

        ax.text(0.01, 0.98, "DIQ \\ IQ",
                transform=ax.transAxes,
                fontsize=8, va="top", ha="left", style="italic")

        fig.suptitle(
            f"{BENCH_LABELS.get(bench, bench)}  "
            f"(green = high IPC, red = low — range {vmin:.3f}–{vmax:.3f})",
            fontsize=11,
        )
        fig.tight_layout()
        figs.append((bench, fig))

    return figs


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", dest="results_file", type=str,
                        default=str(RESULTS_FILE),
                        help="Path to results txt file")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--bar",   dest="mode", action="store_const", const="bar",
                      help="Grouped bar chart (good for small config sets)")
    mode.add_argument("--table", dest="mode", action="store_const", const="table",
                      help="Heatmap table: rows = DIQ, columns = IQ")
    parser.add_argument("--baseline", dest="baseline", type=str, default="160/0",
                        help="Baseline config for bar chart normalisation (default: 160/0)")
    parser.add_argument("-s", dest="save", action="store_true",
                        help="Save each figure to plot_ipc/<bench>_<mode>.png")
    args = parser.parse_args()

    records = parse_results(Path(args.results_file))
    write_csv(records, CSV_OUT)
    print(f"Wrote {CSV_OUT}")

    if args.mode == "bar":
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
            out = PLOT_DIR / f"{bench}_{mode_tag}.png"
            fig.savefig(out, dpi=150)
            print(f"Saved {out}")

    plt.show()
