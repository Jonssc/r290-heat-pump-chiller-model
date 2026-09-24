"""
04_plot_validation.py

Publication-style validation plots. The validation calculation is not repeated.
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
from matplotlib.lines import Line2D


# ============================================================
# 2. FILES USED BY THIS SCRIPT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLOT_STYLE_FILE = PROJECT_ROOT / "00_CONFIG" / "plot_style.py"
TABLE_IO_FILE = PROJECT_ROOT / "00_CONFIG" / "table_io.py"
CONFIG_FILE = PROJECT_ROOT / "00_CONFIG" / "config.py"
INPUT_VALIDATION_ROWS = PROJECT_ROOT / "06_RESULTS" / "validation" / "validation_rows.csv"
OUTPUT_FOLDER = PROJECT_ROOT / "08_THESIS_EXPORT" / "figures" / "validation"


# ============================================================
# 3. PLOT SELECTION
# ============================================================

PLOT_POWER_SCATTER = True
PLOT_RESIDUAL_VS_POWER = True
PLOT_RESIDUAL_VS_CAPACITY = True

# Restored diagnostic plots from the previous validation workflow.
PLOT_FREQUENCY_DIAGNOSTIC = True
PLOT_SUPERHEAT_RESIDUAL = True
PLOT_PROVISIONAL_FREQUENCY = True

PLOT_TIMELINE_PER_UNIT = False


# ============================================================
# 4. MODULE LOADING
# ============================================================

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


style = load_module("plot_style_validation", PLOT_STYLE_FILE)
table_io = load_module("table_io_plot_validation", TABLE_IO_FILE)
config = load_module("config_plot_validation", CONFIG_FILE)


# ============================================================
# 5. STATISTICS / DISPLAY HELPERS
# ============================================================

def regression(x, y):
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    if len(x) < 2 or np.std(x) == 0:
        return np.nan, np.nan, np.nan
    m, b = np.polyfit(x, y, 1)
    yhat = m * x + b
    ssres = np.sum((y - yhat) ** 2)
    sstot = np.sum((y - y.mean()) ** 2)
    return float(m), float(b), float(1 - ssres / sstot if sstot > 0 else np.nan)


def unit_label(unit, group):
    mode = str(group["mode"].iloc[0]).strip().lower()
    return f"HP{int(unit)} {mode}"


def mode_color(group_or_mode):
    if hasattr(group_or_mode, "__getitem__") and not isinstance(group_or_mode, str):
        mode = str(group_or_mode["mode"].iloc[0]).strip().lower()
    else:
        mode = str(group_or_mode).strip().lower()
    return style.MODE_COLOR.get(mode, style.TEAL)


def unit_marker(unit):
    return "o" if int(unit) == 1 else "s"


def scatter_unit(ax, x, y, unit, label, *, size=48, alpha=0.72, zorder=None):
    return ax.scatter(
        x,
        y,
        s=size,
        alpha=alpha,
        color=mode_color(label.split()[-1]),
        marker=unit_marker(unit),
        edgecolors="white",
        linewidths=0.5,
        label=label,
        zorder=zorder,
    )


# ============================================================
# 6. PLOTS
# ============================================================

def main():
    d = table_io.read_table(INPUT_VALIDATION_ROWS)
    d = d[d["model_status"].astype(str).eq("OK")].copy()
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    xcol = "frascold_plus_fans_power_kW"
    ycol = "kiona_chiller_unit_electrical_power_kW"
    residual_col = "kiona_minus_model_kW"

    # --------------------------------------------------------
    # 01 Electrical-power validation
    # --------------------------------------------------------
    if PLOT_POWER_SCATTER:
        g = d.dropna(subset=[xcol, ycol])
        if not g.empty:
            style.setup_plot_theme()
            fig, ax = plt.subplots(figsize=(8.2, 7.2))
            lo = max(0.0, min(g[xcol].min(), g[ycol].min()) * 0.92)
            hi = max(g[xcol].max(), g[ycol].max()) * 1.06
            xx = np.linspace(lo, hi, 300)
            ax.fill_between(xx, 0.90 * xx, 1.10 * xx, color="#E8E8E8", alpha=.55, label="±10% band", zorder=0)
            ax.fill_between(xx, 0.95 * xx, 1.05 * xx, color="#D0D0D0", alpha=.55, label="±5% band", zorder=1)
            ax.plot(xx, xx, "--", color="black", linewidth=1.35, label="1:1 reference", zorder=2)
            fit_text = []

            for unit, gu in g.groupby("unit"):
                x = gu[xcol].to_numpy(float)
                y = gu[ycol].to_numpy(float)
                m, b, r2 = regression(x, y)
                scatter_unit(ax, x, y, unit, unit_label(unit, gu), size=52, zorder=4)
                if np.isfinite(m):
                    xf = np.linspace(x.min(), x.max(), 100)
                    ax.plot(
                        xf,
                        m * xf + b,
                        color=mode_color(gu),
                        linewidth=2.0,
                        zorder=3,
                    )
                    fit_text.append(f"HP{int(unit)}: y={m:.2f}x{b:+.2f}, R²={r2:.3f}")

            ax.set_xlim(lo, hi)
            ax.set_ylim(lo, hi)
            ax.set_aspect("equal", adjustable="box")
            style.style_axis(
                ax,
                "Electrical-power validation",
                "Frascold compressors + unit fans [kW]",
                "Kiona chiller-unit power [kW]",
            )
            ax.legend(loc="upper left")
            if fit_text:
                ax.text(
                    .98,
                    .03,
                    "\n".join(fit_text),
                    transform=ax.transAxes,
                    ha="right",
                    va="bottom",
                    fontsize=16,
                    color=style.TEXT_GREY,
                    bbox=dict(
                        boxstyle="round,pad=.35",
                        facecolor="white",
                        edgecolor=style.BORDER_GREY,
                        alpha=.92,
                    ),
                )
            style.save_figure(fig, OUTPUT_FOLDER / "01_electrical_power_validation.png")

    # --------------------------------------------------------
    # 02 Residual vs predicted power + separate trend lines
    # --------------------------------------------------------
    if PLOT_RESIDUAL_VS_POWER:
        g = d.dropna(subset=[xcol, residual_col])
        if not g.empty:
            style.setup_plot_theme()
            fig, ax = plt.subplots(figsize=(8.4, 5.8))

            for unit, gu in g.groupby("unit"):
                x = gu[xcol].to_numpy(float)
                y = gu[residual_col].to_numpy(float)
                scatter_unit(ax, x, y, unit, unit_label(unit, gu))

                m, b, _ = regression(x, y)
                if np.isfinite(m):
                    xf = np.linspace(np.nanmin(x), np.nanmax(x), 120)
                    ax.plot(
                        xf,
                        m * xf + b,
                        color=mode_color(gu),
                        linewidth=1.9,
                    )

            ax.axhline(0, color="black", linestyle="--", linewidth=1.2)
            style.style_axis(
                ax,
                "Validation residual vs predicted power",
                "Frascold compressors + unit fans [kW]",
                "Kiona − model [kW]",
            )
            ax.legend(loc="best")
            style.save_figure(fig, OUTPUT_FOLDER / "02_residual_vs_model_power.png")

    # --------------------------------------------------------
    # 03 Residual vs capacity request + trend lines and slopes
    # --------------------------------------------------------
    if PLOT_RESIDUAL_VS_CAPACITY:
        g = d.dropna(subset=["capacity_request_percent", residual_col])
        if not g.empty:
            style.setup_plot_theme()
            fig, ax = plt.subplots(figsize=(8.4, 5.8))

            for unit, gu in g.groupby("unit"):
                x = gu["capacity_request_percent"].to_numpy(float)
                y = gu[residual_col].to_numpy(float)
                label = unit_label(unit, gu)
                scatter_unit(ax, x, y, unit, label)

                m, b, _ = regression(x, y)
                if np.isfinite(m):
                    xf = np.linspace(np.nanmin(x), np.nanmax(x), 120)
                    ax.plot(
                        xf,
                        m * xf + b,
                        color=mode_color(gu),
                        linewidth=1.9,
                        label=f"{label} trend: {m:+.3f} kW/%",
                    )

            ax.axhline(0, color="black", linestyle="--", linewidth=1.2)
            style.style_axis(
                ax,
                "Load-dependent validation residual",
                "Kiona capacity request [%]",
                "Kiona − model [kW]",
            )
            ax.legend(loc="best")
            style.save_figure(fig, OUTPUT_FOLDER / "03_residual_vs_capacity_request.png")

    # --------------------------------------------------------
    # 04 Frequency-assumption diagnostic (restored)
    # --------------------------------------------------------
    if PLOT_FREQUENCY_DIAGNOSTIC:
        required = [
            "estimated_frequency_Hz_per_active_circuit",
            "diagnostic_best_fit_frequency_Hz",
        ]
        if all(c in d.columns for c in required):
            g = d.dropna(subset=required)
            if not g.empty:
                style.setup_plot_theme()
                fig, ax = plt.subplots(figsize=(7.7, 6.4))

                lo = min(
                    g[required[0]].min(),
                    g[required[1]].min(),
                ) - 1.0
                hi = max(
                    g[required[0]].max(),
                    g[required[1]].max(),
                ) + 1.0
                ax.plot([lo, hi], [lo, hi], "--", color="black", linewidth=1.2, label="1:1")

                for unit, gu in g.groupby("unit"):
                    scatter_unit(
                        ax,
                        gu[required[0]],
                        gu[required[1]],
                        unit,
                        unit_label(unit, gu),
                        size=50,
                    )

                ax.set_xlim(lo, hi)
                ax.set_ylim(lo, hi)
                ax.set_aspect("equal", adjustable="box")
                style.style_axis(
                    ax,
                    "Frequency-assumption diagnostic",
                    "Provisional frequency [Hz]",
                    "Back-calculated frequency [Hz]",
                )
                # This diagnostic uses shorter, slightly smaller axis labels so
                # the square plot remains readable at thesis figure width.
                ax.xaxis.label.set_size(13)
                ax.yaxis.label.set_size(13)
                ax.legend(loc="upper left")
                style.save_figure(
                    fig,
                    OUTPUT_FOLDER / "04_frequency_assumption_diagnostic.png",
                    bottom=0.10,
                )

    # --------------------------------------------------------
    # 05 Residual vs measured suction superheat (restored)
    # --------------------------------------------------------
    if PLOT_SUPERHEAT_RESIDUAL:
        if "mean_active_superheat_K" in d.columns:
            g = d.dropna(subset=["mean_active_superheat_K", residual_col])
            if not g.empty:
                style.setup_plot_theme()
                fig, ax = plt.subplots(figsize=(8.4, 5.8))

                for unit, gu in g.groupby("unit"):
                    scatter_unit(
                        ax,
                        gu["mean_active_superheat_K"],
                        gu[residual_col],
                        unit,
                        unit_label(unit, gu),
                    )

                ax.axvline(
                    7.0,
                    color="black",
                    linestyle="--",
                    linewidth=1.2,
                    label="Frascold reference: 7 K",
                )
                ax.axhline(0, color=style.TEXT_GREY, linestyle=":", linewidth=1.0)
                style.style_axis(
                    ax,
                    "Residual vs measured suction superheat",
                    "Mean active-circuit superheat [K]",
                    "Kiona − model [kW]",
                )
                ax.legend(loc="best")
                style.save_figure(fig, OUTPUT_FOLDER / "05_superheat_vs_residual.png")

    # --------------------------------------------------------
    # 06 Provisional compressor frequency (restored)
    # --------------------------------------------------------
    if PLOT_PROVISIONAL_FREQUENCY:
        required = [
            "capacity_request_percent",
            "estimated_frequency_Hz_per_active_circuit",
            "active_circuit_count",
        ]
        if all(c in d.columns for c in required):
            g = d.dropna(subset=required)
            if not g.empty:
                style.setup_plot_theme()
                fig, ax = plt.subplots(figsize=(9.4, 5.9))

                for unit, gu in g.groupby("unit"):
                    unit = int(unit)
                    color = mode_color(gu)
                    for nactive, gn in gu.groupby("active_circuit_count"):
                        marker = "o" if int(nactive) == 1 else "D"
                        ax.scatter(
                            gn["capacity_request_percent"],
                            gn["estimated_frequency_Hz_per_active_circuit"],
                            s=48,
                            alpha=.72,
                            color=color,
                            marker=marker,
                            edgecolors="white",
                            linewidths=.5,
                        )

                demand = np.linspace(
                    max(0.0, float(g["capacity_request_percent"].min()) - 2.0),
                    min(100.0, float(g["capacity_request_percent"].max()) + 2.0),
                    240,
                )
                f_one = np.clip(
                    2.0 * config.VALIDATION_COMMAND_TO_HZ * demand,
                    config.VALIDATION_MIN_FREQUENCY_HZ,
                    config.VALIDATION_MAX_FREQUENCY_HZ,
                )
                f_two = np.clip(
                    config.VALIDATION_COMMAND_TO_HZ * demand,
                    config.VALIDATION_MIN_FREQUENCY_HZ,
                    config.VALIDATION_MAX_FREQUENCY_HZ,
                )
                ax.plot(demand, f_one, color=style.TEXT_GREY, linestyle="--", linewidth=1.3)
                ax.plot(demand, f_two, color=style.TEXT_GREY, linestyle=":", linewidth=1.5)

                style.style_axis(
                    ax,
                    "Provisional compressor frequency (not measured)",
                    "Kiona capacity request [%]",
                    "Estimated circuit frequency [Hz]",
                )

                handles = []
                for unit, gu in g.groupby("unit"):
                    handles.append(
                        Line2D(
                            [0], [0],
                            marker=unit_marker(unit),
                            color="none",
                            markerfacecolor=mode_color(gu),
                            markeredgecolor="white",
                            markersize=8,
                            label=unit_label(unit, gu),
                        )
                    )
                handles.extend([
                    Line2D([0], [0], marker="o", color=style.TEXT_GREY, linestyle="none", markersize=7, label="1 active circuit"),
                    Line2D([0], [0], marker="D", color=style.TEXT_GREY, linestyle="none", markersize=7, label="2 active circuits"),
                    Line2D([0], [0], color=style.TEXT_GREY, linestyle="--", label="1-circuit control law"),
                    Line2D([0], [0], color=style.TEXT_GREY, linestyle=":", label="2-circuit control law"),
                ])
                ax.legend(handles=handles, loc="upper left", ncol=2)
                style.save_figure(fig, OUTPUT_FOLDER / "06_provisional_compressor_frequency.png")

    # --------------------------------------------------------
    # Optional timeline plots retained from current code
    # --------------------------------------------------------
    if PLOT_TIMELINE_PER_UNIT and "start_time" in d.columns:
        d["start_time"] = pd.to_datetime(d["start_time"], errors="coerce")
        for unit, g in d.groupby("unit"):
            g = g.dropna(subset=["start_time", xcol, ycol]).sort_values("start_time")
            if g.empty:
                continue
            style.setup_plot_theme()
            fig, ax = plt.subplots(figsize=(11, 5))
            ax.plot(g["start_time"], g[ycol], color=mode_color(g["mode"].iloc[0]), linewidth=1.5, marker="o", markersize=3.5, label="Kiona")
            ax.plot(g["start_time"], g[xcol], color=style.YELLOW, linewidth=1.5, marker="o", markersize=3.2, label="Frascold + fans")
            style.style_axis(
                ax,
                f"HP{int(unit)}: Kiona vs model electrical power",
                "Stable-period start time",
                "Electrical power [kW]",
            )
            ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0))
            fig.autofmt_xdate(rotation=25)
            style.save_figure(
                fig,
                OUTPUT_FOLDER / f"07_HP{int(unit)}_power_timeline.png",
                right=.82,
            )


if __name__ == "__main__":
    main()
