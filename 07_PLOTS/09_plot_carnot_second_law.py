"""
09_plot_carnot_second_law.py

Plots the precomputed Carnot / second-law result tables.
No Carnot or Chiller Unit calculations are performed here.
"""

# ============================================================
# 1. IMPORTS
# ============================================================

from pathlib import Path
import importlib.util
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# 2. FILES USED BY THIS SCRIPT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONFIG_FILE = PROJECT_ROOT / "00_CONFIG" / "config.py"
TABLE_IO_FILE = PROJECT_ROOT / "00_CONFIG" / "table_io.py"
PLOT_STYLE_FILE = PROJECT_ROOT / "00_CONFIG" / "plot_style.py"

INPUT_ROWS = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "carnot"
    / "carnot_second_law_rows.csv"
)

INPUT_SUMMARY = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "carnot"
    / "carnot_second_law_summary.csv"
)

OUTPUT_FOLDER = (
    PROJECT_ROOT
    / "08_THESIS_EXPORT"
    / "figures"
    / "carnot"
)


# ============================================================
# 3. PLOT SELECTION
# ============================================================

PLOT_CARNOT_VS_REAL = True
PLOT_SECOND_LAW_EFFICIENCY = True
PLOT_ETAII_VS_REFRIGERANT_LIFT = True


# ============================================================
# 4. MODULE LOADING
# ============================================================

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


config = load_module("config_plot_carnot", CONFIG_FILE)
table_io = load_module("table_io_plot_carnot", TABLE_IO_FILE)
style = load_module("style_plot_carnot", PLOT_STYLE_FILE)

style.setup_plot_theme()


# ============================================================
# 5. HELPERS
# ============================================================

def read_optional(path):
    if path.exists():
        return table_io.read_table(path)

    csv = path.with_suffix(".csv")

    if csv.exists():
        return table_io.read_table(csv)

    return pd.DataFrame()


def save(fig, filename, right=0.98):
    style.save_figure(
        fig,
        OUTPUT_FOLDER / filename,
        dpi=config.PLOT_DPI,
        right=right,
    )


def annotate_bars(ax, bars, *, fmt="{:.2f}", fontsize=style.BAR_VALUE_FONTSIZE, offset_fraction=0.012):
    """Place value labels slightly above each bar."""
    values = [float(bar.get_height()) for bar in bars]
    finite_values = [abs(v) for v in values if np.isfinite(v)]
    value_span = max(finite_values) if finite_values else 1.0
    offset = max(value_span * offset_fraction, 0.02)

    for bar, value in zip(bars, values):
        if not np.isfinite(value):
            continue
        y = value + offset if value >= 0 else value - offset
        va = "bottom" if value >= 0 else "top"
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            y,
            fmt.format(value),
            ha="center",
            va=va,
            fontsize=fontsize,
        )


# ============================================================
# 6. PLOTS
# ============================================================

def main():
    rows = read_optional(
        INPUT_ROWS
    )

    summary = read_optional(
        INPUT_SUMMARY
    )

    if PLOT_CARNOT_VS_REAL and not summary.empty:
        fig, ax = plt.subplots(
            figsize=(9.6, 5.8)
        )

        x = np.arange(
            len(summary)
        )

        width = 0.23

        bars_carnot = ax.bar(
            x - width,
            summary["refrigerant_Carnot_COP_or_EER"],
            width,
            label="Carnot",
            color=style.YELLOW,
        )

        bars_frascold = ax.bar(
            x,
            summary["Frascold_compressor_COP_or_EER"],
            width,
            label="Compressor",
            color=style.TEAL,
        )

        bars_unit = ax.bar(
            x + width,
            summary["field_referenced_unit_proxy_COP_or_EER"],
            width,
            label="Field proxy",
            color=style.POINT_GREY,
        )

        style.style_axis(
            ax,
            title="Carnot benchmark vs modeled / field-referenced performance",
            ylabel="COP / EER [-]",
            grid_axis="y",
        )

        ax.set_xticks(
            x
        )

        ax.set_xticklabels(
            [
                str(mode).capitalize()
                for mode in summary["mode"]
            ]
        )

        annotate_bars(ax, bars_carnot)
        annotate_bars(ax, bars_frascold)
        annotate_bars(ax, bars_unit)

        ax.legend(
            loc="upper left",
            bbox_to_anchor=(1.01, 1.0),
            borderaxespad=0.0,
        )

        save(
            fig,
            "01_carnot_vs_performance.png",
            right=0.82,
        )

    if PLOT_SECOND_LAW_EFFICIENCY and not summary.empty:
        fig, ax = plt.subplots(
            figsize=(9.4, 5.7)
        )

        x = np.arange(
            len(summary)
        )

        width = 0.34

        bars_comp = ax.bar(
            x - width / 2,
            summary["etaII_refrigerant_compressor_percent"],
            width,
            color=style.TEAL,
            label="Compressor",
        )

        bars_unit = ax.bar(
            x + width / 2,
            summary["etaII_refrigerant_unit_proxy_percent"],
            width,
            color=style.POINT_GREY,
            label="Field proxy",
        )

        style.style_axis(
            ax,
            title="Second-law efficiency at refrigerant temperature levels",
            ylabel="Second-law efficiency [%]",
            grid_axis="y",
        )

        ax.set_xticks(
            x
        )

        ax.set_xticklabels(
            [
                str(mode).capitalize()
                for mode in summary["mode"]
            ]
        )

        annotate_bars(ax, bars_comp, fmt="{:.1f}")
        annotate_bars(ax, bars_unit, fmt="{:.1f}")

        # Keep the legend completely outside the data region so it never
        # overlaps the right-hand heating bars.
        ax.legend(
            loc="upper left",
            bbox_to_anchor=(1.01, 1.0),
            borderaxespad=0.0,
        )

        save(
            fig,
            "02_second_law_efficiency.png",
            right=0.84,
        )

    if PLOT_ETAII_VS_REFRIGERANT_LIFT and not rows.empty:
        fig, ax = plt.subplots(
            figsize=(9.5, 5.8)
        )

        for mode, group in rows.groupby("mode"):
            ax.scatter(
                group["mean_R290_lift_K"],
                group["etaII_refrigerant_compressor_percent"],
                s=45,
                alpha=0.60,
                color=style.MODE_COLOR.get(
                    mode,
                    style.TEAL,
                ),
                edgecolors="white",
                linewidths=0.4,
                label=str(mode).capitalize(),
            )

        style.style_axis(
            ax,
            title="Second-law efficiency vs refrigerant temperature lift",
            xlabel="R290 saturation-temperature lift [K]",
            ylabel="Compressor second-law efficiency [%]",
        )

        ax.legend(
            loc="best"
        )

        save(
            fig,
            "03_etaII_vs_refrigerant_lift.png",
        )

    pass


if __name__ == "__main__":
    main()
