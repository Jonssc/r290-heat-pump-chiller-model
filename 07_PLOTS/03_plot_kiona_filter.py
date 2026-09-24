"""
03_plot_kiona_filter.py

Plots accepted Kiona stable periods from the stored result table and visualizes
how the accepted stable periods map onto the raw electrical-power time series.
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
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


# ============================================================
# 2. FILES USED BY THIS SCRIPT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLOT_STYLE_FILE = PROJECT_ROOT / "00_CONFIG" / "plot_style.py"
TABLE_IO_FILE = PROJECT_ROOT / "00_CONFIG" / "table_io.py"
INPUT_STABLE_PERIODS = PROJECT_ROOT / "02_PROCESSED_DATA" / "kiona_stable_periods.csv"
INPUT_CLEAN_KIONA = PROJECT_ROOT / "02_PROCESSED_DATA" / "kiona_detailed_clean.csv"
OUTPUT_FOLDER = PROJECT_ROOT / "08_THESIS_EXPORT" / "figures" / "kiona"


# ============================================================
# 3. PLOT SELECTION
# ============================================================

PLOT_PRESSURE_MAP = True
PLOT_POWER_VS_PRESSURE_RATIO = True
PLOT_OUTDOOR_VS_POWER = False
PLOT_HP1_TIMESERIES = True
PLOT_HP2_TIMESERIES = True
PLOT_PERIOD_COVERAGE = True

# Low-load stable periods are shown separately for the cooling unit because
# they were used as an explicit visual diagnostic in earlier thesis versions.
HP2_LOW_LOAD_CAPACITY_REQUEST_MAX_PERCENT = 18.0


# ============================================================
# 4. MODULE LOADING
# ============================================================

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

style = load_module("plot_style_kiona", PLOT_STYLE_FILE)
table_io = load_module("table_io_plot_kiona", TABLE_IO_FILE)


# ============================================================
# 5. HELPERS
# ============================================================

def _prepare_inputs():
    stable = table_io.read_table(INPUT_STABLE_PERIODS)
    raw = table_io.read_table(INPUT_CLEAN_KIONA)

    for frame in (stable, raw):
        if "timestamp" in frame.columns:
            frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    stable["start_time"] = pd.to_datetime(stable["start_time"], errors="coerce")
    stable["end_time"] = pd.to_datetime(stable["end_time"], errors="coerce")

    raw = raw.sort_values("timestamp").reset_index(drop=True)
    stable = stable.sort_values(["unit", "start_time"]).reset_index(drop=True)
    return raw, stable


def _shade_periods(ax, periods, *, color, alpha, label=None, zorder=1):
    label_used = False
    for _, row in periods.iterrows():
        start = row["start_time"]
        end = row["end_time"] + pd.Timedelta(minutes=5)
        if pd.isna(start) or pd.isna(end):
            continue
        ax.axvspan(
            start,
            end,
            color=color,
            alpha=alpha,
            zorder=zorder,
            label=label if (label is not None and not label_used) else None,
        )
        label_used = True


def _mode_color(group_or_mode):
    if hasattr(group_or_mode, "__getitem__") and not isinstance(group_or_mode, str):
        mode = str(group_or_mode["mode"].iloc[0]).strip().lower()
    else:
        mode = str(group_or_mode).strip().lower()
    return style.MODE_COLOR.get(mode, style.TEAL)


def _style_time_axis(ax):
    locator = mdates.AutoDateLocator(minticks=7, maxticks=10)
    formatter = mdates.DateFormatter("%d %b")
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    ax.get_xaxis().get_offset_text().set_visible(False)
    ax.tick_params(axis="x", rotation=20)


def _save_timeseries_figure(fig, filename, handles, ncol):
    """Save time-series plots without squeezing the axes for the outside legend."""
    fig.subplots_adjust(left=0.08, right=0.985, top=0.90, bottom=0.30)
    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.010),
        ncol=ncol,
        frameon=False,
    )
    path = OUTPUT_FOLDER / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    style.save_png(fig, path, dpi=220)
    plt.close(fig)


# ============================================================
# 6. PLOTS
# ============================================================

def main():
    raw, g = _prepare_inputs()
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    if PLOT_PRESSURE_MAP:
        style.setup_plot_theme(); fig, ax = plt.subplots(figsize=(8.4, 6.3))
        markers = {1: "o", 2: "^"}
        for unit, gu in g.groupby("unit"):
            for c in (1, 2):
                active = gu[f"c{c}_active"].astype(bool)
                ax.scatter(
                    gu.loc[active, f"mean_evaporating_pressure_c{c}_bar"],
                    gu.loc[active, f"mean_condensing_pressure_c{c}_bar"],
                    s=56,
                    alpha=0.78,
                    color=_mode_color(gu),
                    marker=markers[c],
                    edgecolors="white",
                    linewidths=0.5,
                    label=f"HP{int(unit)} C{c}",
                )
        style.style_axis(
            ax,
            "Stable-period mean refrigerant pressures",
            "Mean evaporating pressure [bar]",
            "Mean condensing pressure [bar]",
        )
        ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0))
        style.save_figure(fig, OUTPUT_FOLDER / "01_stable_pressure_map.png", right=0.82)

    if PLOT_POWER_VS_PRESSURE_RATIO:
        style.setup_plot_theme(); fig, ax = plt.subplots(figsize=(8.4, 6.1))
        for unit, gu in g.groupby("unit"):
            ax.scatter(
                gu["mean_active_pressure_ratio"],
                gu["mean_electrical_power_kW"],
                s=58,
                alpha=0.80,
                color=_mode_color(gu),
                edgecolors="white",
                linewidths=0.5,
                label=f"HP{int(unit)} {gu['mode'].iloc[0]}",
            )
        style.style_axis(
            ax,
            "Stable operating points: pressure ratio vs electrical input",
            "Mean active pressure ratio [-]",
            "Mean whole-unit electrical power [kW]",
        )
        ax.legend(loc="best")
        style.save_figure(fig, OUTPUT_FOLDER / "02_power_vs_pressure_ratio.png")

    if PLOT_OUTDOOR_VS_POWER:
        style.setup_plot_theme(); fig, ax = plt.subplots(figsize=(8.4, 6.1))
        for unit, gu in g.groupby("unit"):
            ax.scatter(
                gu["mean_outdoor_temp_C"],
                gu["mean_electrical_power_kW"],
                s=58,
                alpha=0.80,
                color=_mode_color(gu),
                edgecolors="white",
                linewidths=0.5,
                label=f"HP{int(unit)} {gu['mode'].iloc[0]}",
            )
        style.style_axis(
            ax,
            "Stable operating points: outdoor temperature vs electrical input",
            "Mean outdoor temperature [°C]",
            "Mean whole-unit electrical power [kW]",
        )
        ax.legend(loc="best")
        style.save_figure(fig, OUTPUT_FOLDER / "03_outdoor_vs_power.png")

    if PLOT_HP1_TIMESERIES:
        q = g[g["unit"] == 1].copy()
        r = raw[["timestamp", "HP1_electrical_power_kW"]].copy()
        r = r.rename(columns={"HP1_electrical_power_kW": "electrical_power_kW"})

        style.setup_plot_theme(); fig, ax = plt.subplots(figsize=(12.8, 6.2))
        _shade_periods(ax, q, color="#BFE3FA", alpha=0.42, label="Accepted stable period", zorder=1)
        ax.plot(
            r["timestamp"],
            r["electrical_power_kW"],
            color=style.HEATING_COLOR,
            linewidth=1.3,
            alpha=0.90,
            zorder=2,
            label="Whole-unit electrical power",
        )
        style.style_axis(
            ax,
            "Heat Pump 1: electrical power and accepted stable periods",
            "Time",
            "Electrical power [kW]",
        )
        ax.set_ylim(-0.2, max(1.0, np.nanmax(r["electrical_power_kW"]) * 1.05))
        _style_time_axis(ax)
        handles = [
            Line2D([0], [0], color=style.HEATING_COLOR, linewidth=1.3, label="Whole-unit electrical power"),
            Patch(facecolor="#BFE3FA", edgecolor="#BFE3FA", alpha=0.42, label="Accepted stable period"),
        ]
        _save_timeseries_figure(
            fig,
            "04_hp1_power_and_accepted_stable_periods.png",
            handles,
            ncol=2,
        )

    if PLOT_HP2_TIMESERIES:
        q = g[g["unit"] == 2].copy()
        low_load = q[q["mean_capacity_request_percent"] <= HP2_LOW_LOAD_CAPACITY_REQUEST_MAX_PERCENT].copy()
        r = raw[["timestamp", "HP2_electrical_power_kW"]].copy()
        r = r.rename(columns={"HP2_electrical_power_kW": "electrical_power_kW"})

        style.setup_plot_theme(); fig, ax = plt.subplots(figsize=(12.8, 6.2))
        _shade_periods(ax, q, color="#BFE3FA", alpha=0.40, label="Accepted stable period", zorder=1)
        if not low_load.empty:
            _shade_periods(ax, low_load, color="#F8E9B5", alpha=0.45, label="Low-load accepted period", zorder=1.1)
        ax.plot(
            r["timestamp"],
            r["electrical_power_kW"],
            color=style.COOLING_COLOR,
            linewidth=1.3,
            alpha=0.90,
            zorder=2,
            label="Whole-unit electrical power",
        )
        style.style_axis(
            ax,
            "Heat Pump 2: electrical power and accepted stable periods",
            "Time",
            "Electrical power [kW]",
        )
        ax.set_ylim(-0.2, max(1.0, np.nanmax(r["electrical_power_kW"]) * 1.05))
        _style_time_axis(ax)
        handles = [
            Line2D([0], [0], color=style.COOLING_COLOR, linewidth=1.3, label="Whole-unit electrical power"),
            Patch(facecolor="#BFE3FA", edgecolor="#BFE3FA", alpha=0.40, label="Accepted stable period"),
        ]
        if not low_load.empty:
            handles.append(
                Patch(facecolor="#F8E9B5", edgecolor="#F8E9B5", alpha=0.45, label="Low-load accepted period")
            )
        _save_timeseries_figure(
            fig,
            "05_hp2_power_and_accepted_stable_periods.png",
            handles,
            ncol=3 if len(handles) == 3 else 2,
        )

    if PLOT_PERIOD_COVERAGE:
        q = (
            g.sort_values(["unit", "start_time"])
            .reset_index(drop=True)
            .copy()
        )
        q["bar_index"] = np.arange(len(q))

        style.setup_plot_theme(); fig, ax = plt.subplots(figsize=(12.0, 5.4))
        hp1 = q[q["unit"] == 1]
        hp2 = q[q["unit"] == 2]
        ax.bar(
            hp1["bar_index"],
            hp1["nominal_sample_coverage_minutes"],
            color=style.HEATING_COLOR,
            width=0.76,
            edgecolor="white",
            linewidth=0.3,
            alpha=0.90,
            label="HP1 heating",
        )
        ax.bar(
            hp2["bar_index"],
            hp2["nominal_sample_coverage_minutes"],
            color=style.COOLING_COLOR,
            width=0.76,
            edgecolor="white",
            linewidth=0.3,
            alpha=0.90,
            label="HP2 cooling",
        )
        title = (
            "Accepted stable-period sample coverage\n"
            f"HP1: {len(hp1)} periods, HP2: {len(hp2)} periods"
        )
        style.style_axis(
            ax,
            title,
            "Accepted stable periods",
            "Sample coverage [min]",
            grid_axis="y",
        )
        ax.set_xticks([])
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=2)
        style.save_figure(fig, OUTPUT_FOLDER / "06_accepted_stable_period_sample_coverage.png", bottom=0.12)


if __name__ == "__main__":
    main()
