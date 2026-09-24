"""
07_plot_buffer_cycling.py

Plots ideal buffer cycling from the precomputed buffer result table.
No thermodynamic model is run here.
"""

# ============================================================
# 1. IMPORTS
# ============================================================

from pathlib import Path
import importlib.util
import sys

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


# ============================================================
# 2. FILES USED BY THIS SCRIPT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONFIG_FILE = PROJECT_ROOT / "00_CONFIG" / "config.py"
TABLE_IO_FILE = PROJECT_ROOT / "00_CONFIG" / "table_io.py"
PLOT_STYLE_FILE = PROJECT_ROOT / "00_CONFIG" / "plot_style.py"

INPUT_BUFFER_TABLE = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "optimization"
    / "buffer"
    / "01_buffer_cycling_sensitivity.csv"
)

OUTPUT_FOLDER = (
    PROJECT_ROOT
    / "08_THESIS_EXPORT"
    / "figures"
    / "optimization"
    / "buffer"
)


# ============================================================
# 3. PLOT SELECTION
# ============================================================

PLOT_STARTS_PER_DAY = True
PLOT_RUNTIME_PER_CYCLE = True
PLOT_DAILY_RUNTIME = False
PLOT_BUFFER_VOLUME_EXTRAS = True


# ============================================================
# 4. MODULE LOADING
# ============================================================

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


config = load_module("config_plot_buffer", CONFIG_FILE)
table_io = load_module("table_io_plot_buffer", TABLE_IO_FILE)
style = load_module("style_plot_buffer", PLOT_STYLE_FILE)

style.setup_plot_theme()


# ============================================================
# 5. INPUT
# ============================================================

def load_data():
    if INPUT_BUFFER_TABLE.exists():
        return table_io.read_table(INPUT_BUFFER_TABLE)

    csv = INPUT_BUFFER_TABLE.with_suffix(".csv")

    if csv.exists():
        return table_io.read_table(csv)

    raise FileNotFoundError(
        "Run 05_ANALYSIS/08_generate_buffer_cycling.py first."
    )


# ============================================================
# 6. HELPERS
# ============================================================

def _sorted_unique(values):
    return sorted(float(v) for v in pd.Series(values).dropna().unique())


def _installed_volume(mode):
    return (
        float(config.BUFFER_TANK_HEATING_INSTALLED_L)
        if mode == "heating"
        else float(config.BUFFER_TANK_COOLING_INSTALLED_L)
    )


def _curve_for_load(q, load_fraction):
    return q[
        q["load_fraction_of_Qmin"].round(4).eq(round(float(load_fraction), 4))
    ].sort_values("buffer_volume_L")


def _buffer_palette():
    # Use the same opaque Matplotlib color cycle as the volume-based 03/04 plots.
    return list(plt.rcParams["axes.prop_cycle"].by_key().get("color", []))


def _add_installed_line_to_legend(ax, installed):
    handles, labels = ax.get_legend_handles_labels()
    handles.append(
        Line2D(
            [0],
            [0],
            color="black",
            linestyle="--",
            linewidth=1.6,
        )
    )
    labels.append(f"Installed {installed:.0f} L")
    ax.legend(
        handles,
        labels,
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        borderaxespad=0.0,
    )


# ============================================================
# 7. ORIGINAL PLOTS
# ============================================================

def plot_original_views(q, mode, installed):
    if PLOT_STARTS_PER_DAY:
        fig, ax = plt.subplots(figsize=(9.8, 5.8))

        for color_index, (volume, group) in enumerate(q.groupby("buffer_volume_L")):
            group = group.sort_values("load_fraction_of_Qmin")

            linewidth = 3.0 if abs(float(volume) - installed) < 1e-9 else 1.5
            palette = _buffer_palette()
            color = palette[color_index % len(palette)] if palette else None

            ax.plot(
                100.0 * group["load_fraction_of_Qmin"],
                group["starts_per_day"],
                marker="o",
                linewidth=linewidth,
                alpha=1.0,
                color=color,
                label=f"{float(volume):.0f} L",
            )

        style.style_axis(
            ax,
            title=f"{mode.capitalize()}: ideal buffer cycling",
            xlabel="Average load [% of minimum one-circuit capacity]",
            ylabel="Starts per day [-]",
        )

        ax.legend(
            loc="upper left",
            bbox_to_anchor=(1.01, 1.0),
            borderaxespad=0.0,
            title="Buffer volume",
        )

        style.save_figure(
            fig,
            OUTPUT_FOLDER / f"01_{mode}_buffer_starts_per_day.png",
            dpi=config.PLOT_DPI,
            right=0.80,
        )

    if PLOT_RUNTIME_PER_CYCLE:
        fig, ax = plt.subplots(figsize=(9.8, 5.8))

        for color_index, (volume, group) in enumerate(q.groupby("buffer_volume_L")):
            group = group.sort_values("load_fraction_of_Qmin")

            linewidth = 3.0 if abs(float(volume) - installed) < 1e-9 else 1.5
            palette = _buffer_palette()
            color = palette[color_index % len(palette)] if palette else None

            ax.plot(
                100.0 * group["load_fraction_of_Qmin"],
                group["heat_pump_runtime_per_cycle_min"],
                marker="o",
                linewidth=linewidth,
                alpha=1.0,
                color=color,
                label=f"{float(volume):.0f} L",
            )

        style.style_axis(
            ax,
            title=f"{mode.capitalize()}: runtime per buffer cycle",
            xlabel="Average load [% of minimum one-circuit capacity]",
            ylabel="Heat-pump runtime per cycle [min]",
        )

        ax.legend(
            loc="upper left",
            bbox_to_anchor=(1.01, 1.0),
            borderaxespad=0.0,
            title="Buffer volume",
        )

        style.save_figure(
            fig,
            OUTPUT_FOLDER / f"02_{mode}_buffer_runtime_per_cycle.png",
            dpi=config.PLOT_DPI,
            right=0.80,
        )

    if PLOT_DAILY_RUNTIME:
        fig, ax = plt.subplots(figsize=(9.3, 5.5))

        installed_data = q[
            q["is_installed_volume"].astype(str).str.lower().isin(["true", "1"])
        ].sort_values("load_fraction_of_Qmin")

        ax.plot(
            100.0 * installed_data["load_fraction_of_Qmin"],
            installed_data["heat_pump_runtime_hours_per_day"],
            marker="o",
            linewidth=2.2,
            color=style.MODE_COLOR[mode],
        )

        style.style_axis(
            ax,
            title=f"{mode.capitalize()}: ideal daily runtime",
            xlabel="Average load [% of minimum one-circuit capacity]",
            ylabel="Heat-pump runtime [h/day]",
        )

        style.save_figure(
            fig,
            OUTPUT_FOLDER / f"03_{mode}_buffer_daily_runtime.png",
            dpi=config.PLOT_DPI,
        )


# ============================================================
# 8. EXTRA BUFFER-VOLUME PLOTS
# ============================================================

def plot_runtime_vs_volume(q, mode, installed):
    selected_loads = [0.10, 0.25, 0.50, 0.75, 0.90]

    fig, ax = plt.subplots(figsize=(10.8, 6.0))

    for load_fraction in selected_loads:
        curve = _curve_for_load(q, load_fraction)
        if curve.empty:
            continue

        ax.plot(
            curve["buffer_volume_L"],
            curve["heat_pump_runtime_per_cycle_min"],
            marker="o",
            linewidth=2.0,
            label=f"Load = {load_fraction * 100:.0f}% of Qmin",
        )

    ax.axvline(installed, color="black", linestyle="--", linewidth=1.6)

    style.style_axis(
        ax,
        title=f"{mode.capitalize()}: buffer volume vs compressor run time per start",
        xlabel="Total buffer volume [L]",
        ylabel="Compressor on-time per cycle [min]",
    )

    x_values = _sorted_unique(q["buffer_volume_L"])
    ax.set_xticks(x_values)
    ax.tick_params(axis="x", labelrotation=90, labelsize=16)
    plt.setp(ax.get_xticklabels(), ha="center", va="top")

    _add_installed_line_to_legend(ax, installed)

    style.save_figure(
        fig,
        OUTPUT_FOLDER / f"03_{mode}_buffer_runtime_vs_volume.png",
        dpi=config.PLOT_DPI,
        right=0.74,
    )


def plot_starts_vs_volume(q, mode, installed):
    pair_definitions = [
        (0.10, 0.90, "Load = 10% or 90% of Qmin"),
        (0.25, 0.75, "Load = 25% or 75% of Qmin"),
        (0.50, None, "Load = 50% of Qmin"),
    ]

    fig, ax = plt.subplots(figsize=(12.0, 6.2))

    for left_load, right_load, label in pair_definitions:
        left_curve = _curve_for_load(q, left_load)
        if left_curve.empty:
            continue

        plot_curve = left_curve.copy()

        if right_load is not None:
            right_curve = _curve_for_load(q, right_load)
            if not right_curve.empty:
                merged = left_curve.merge(
                    right_curve[["buffer_volume_L", "starts_per_day"]],
                    on="buffer_volume_L",
                    suffixes=("_left", "_right"),
                )
                plot_curve = pd.DataFrame({
                    "buffer_volume_L": merged["buffer_volume_L"],
                    "starts_per_day": 0.5 * (
                        merged["starts_per_day_left"]
                        + merged["starts_per_day_right"]
                    ),
                })

        ax.plot(
            plot_curve["buffer_volume_L"],
            plot_curve["starts_per_day"],
            marker="o",
            linewidth=2.0,
            label=label,
        )

    ax.axvline(installed, color="black", linestyle="--", linewidth=1.6)

    style.style_axis(
        ax,
        title=f"{mode.capitalize()}: buffer volume vs compressor starts",
        xlabel="Total buffer volume [L]",
        ylabel="Starts per day [-]",
    )

    x_values = _sorted_unique(q["buffer_volume_L"])
    ax.set_xticks(x_values)
    ax.tick_params(axis="x", labelrotation=90, labelsize=16)
    plt.setp(ax.get_xticklabels(), ha="center", va="top")

    _add_installed_line_to_legend(ax, installed)

    style.save_figure(
        fig,
        OUTPUT_FOLDER / f"04_{mode}_buffer_starts_vs_volume.png",
        dpi=config.PLOT_DPI,
        right=0.74,
    )


def plot_extra_views(q, mode, installed):
    if not PLOT_BUFFER_VOLUME_EXTRAS:
        return

    plot_runtime_vs_volume(q, mode, installed)
    plot_starts_vs_volume(q, mode, installed)


# ============================================================
# 9. MAIN
# ============================================================

def plot_mode(data, mode):
    q = data[data["mode"].astype(str).str.lower().eq(mode)].copy()

    if q.empty:
        return

    installed = _installed_volume(mode)

    plot_original_views(q, mode, installed)
    plot_extra_views(q, mode, installed)


def main():
    data = load_data()

    for mode in ("heating", "cooling"):
        plot_mode(data, mode)

    pass


if __name__ == "__main__":
    main()
