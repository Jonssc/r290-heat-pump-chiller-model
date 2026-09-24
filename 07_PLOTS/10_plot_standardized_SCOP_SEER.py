"""
10_plot_standardized_SCOP_SEER.py

Plots precomputed standardized active-mode seasonal results.
No thermodynamic or seasonal calculations occur in this script.

The four standardized heating and cooling anchor temperatures are shown as
paired unit-vs-Carnot bar charts.  The former two-point anchor scatter plots
are intentionally retired because they hid the four underlying SCOP/SEER
anchor conditions and were not useful for the final thesis figures.
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

INPUT_ANCHORS = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "carnot"
    / "standardized_anchor_points.csv"
)

INPUT_BINS = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "carnot"
    / "standardized_seasonal_bins.csv"
)

INPUT_SUMMARY = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "carnot"
    / "standardized_SCOP_SEER_summary.csv"
)

OUTPUT_FOLDER = (
    PROJECT_ROOT
    / "08_THESIS_EXPORT"
    / "figures"
    / "carnot"
    / "standardized"
)


# ============================================================
# 3. PLOT SELECTION
# ============================================================

PLOT_HEATING_COP_CARNOT = True
PLOT_COOLING_EER_CARNOT = True
PLOT_SEASONAL_SUMMARY = True
PLOT_STAGING = False


# ============================================================
# 4. MODULE LOADING
# ============================================================

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


config = load_module("config_plot_standard", CONFIG_FILE)
table_io = load_module("table_io_plot_standard", TABLE_IO_FILE)
style = load_module("style_plot_standard", PLOT_STYLE_FILE)

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


def remove_retired_anchor_plots():
    """Remove stale images from the superseded two-point plot design."""
    for filename in (
        "01_standard_anchor_performance.png",
        "02_standard_anchor_etaII.png",
    ):
        path = OUTPUT_FOLDER / filename
        if path.exists():
            path.unlink()


def anchor_comparison_plot(
    anchors,
    *,
    mode,
    expected_temperatures,
    title,
    ylabel,
    unit_label,
    unit_color,
    filename,
):
    q = anchors[
        anchors["mode"].astype(str).str.lower().eq(mode)
    ].copy()

    if q.empty:
        return

    q["outdoor_C"] = pd.to_numeric(
        q["outdoor_C"],
        errors="coerce",
    )
    q["COP_or_EER"] = pd.to_numeric(
        q["COP_or_EER"],
        errors="coerce",
    )
    q["Carnot_COP_or_EER"] = pd.to_numeric(
        q["Carnot_COP_or_EER"],
        errors="coerce",
    )

    q = q.dropna(
        subset=[
            "outdoor_C",
            "COP_or_EER",
            "Carnot_COP_or_EER",
        ]
    )

    # Use the configured standard anchor order explicitly.  This makes the
    # plot deterministic and prevents any accidental sorting/NaN behaviour
    # from changing the SCOP/SEER comparison sequence.
    rows = []
    for temperature in expected_temperatures:
        match = q[
            np.isclose(
                q["outdoor_C"].to_numpy(float),
                float(temperature),
            )
        ]
        if not match.empty:
            rows.append(match.iloc[0])

    if not rows:
        return

    q = pd.DataFrame(rows).reset_index(drop=True)

    x = np.arange(len(q), dtype=float)
    width = 0.36

    fig, ax = plt.subplots(
        figsize=(10.0, 5.9)
    )

    unit_bars = ax.bar(
        x - width / 2,
        q["COP_or_EER"].to_numpy(float),
        width,
        color=unit_color,
        label=unit_label,
    )

    carnot_bars = ax.bar(
        x + width / 2,
        q["Carnot_COP_or_EER"].to_numpy(float),
        width,
        color=style.POINT_GREY,
        label="Carnot",
    )

    for bars in (unit_bars, carnot_bars):
        for bar in bars:
            value = float(bar.get_height())
            if np.isfinite(value):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    value,
                    f"{value:.2f}",
                    ha="center",
                    va="bottom",
                    fontsize=style.BAR_VALUE_FONTSIZE,
                )

    max_value = np.nanmax(
        np.r_[q["COP_or_EER"].to_numpy(float), q["Carnot_COP_or_EER"].to_numpy(float)]
    )
    ax.set_ylim(0, max_value * 1.16)

    style.style_axis(
        ax,
        title=title,
        xlabel="Outdoor temperature [°C]",
        ylabel=ylabel,
        grid_axis="y",
    )

    ax.set_xticks(x)
    ax.set_xticklabels(
        [
            f"{temperature:g} °C"
            for temperature in q["outdoor_C"].to_numpy(float)
        ]
    )

    ax.legend(
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        borderaxespad=0.0,
    )

    save(
        fig,
        filename,
        right=0.82,
    )


# ============================================================
# 6. PLOTS
# ============================================================

def main():
    remove_retired_anchor_plots()

    anchors = read_optional(
        INPUT_ANCHORS
    )

    bins = read_optional(
        INPUT_BINS
    )

    summary = read_optional(
        INPUT_SUMMARY
    )

    if PLOT_HEATING_COP_CARNOT and not anchors.empty:
        anchor_comparison_plot(
            anchors,
            mode="heating",
            expected_temperatures=(
                config.STANDARD_HEATING_ANCHOR_OUTDOOR_C
            ),
            title="Heating COP compared with Carnot at SCOP anchor temperatures",
            ylabel="COP [-]",
            unit_label="Chiller unit",
            unit_color=style.HEATING_COLOR,
            filename="01_heating_COP_vs_Carnot_standard_anchors.png",
        )

    if PLOT_COOLING_EER_CARNOT and not anchors.empty:
        anchor_comparison_plot(
            anchors,
            mode="cooling",
            expected_temperatures=(
                config.STANDARD_COOLING_ANCHOR_OUTDOOR_C
            ),
            title="Cooling EER compared with Carnot at SEER anchor temperatures",
            ylabel="EER [-]",
            unit_label="Chiller unit",
            unit_color=style.COOLING_COLOR,
            filename="02_cooling_EER_vs_Carnot_standard_anchors.png",
        )

    if PLOT_SEASONAL_SUMMARY and not summary.empty:
        fig, ax = plt.subplots(
            figsize=(9.4, 5.7)
        )

        labels = [
            (
                f"{str(row.mode).capitalize()}\n"
                f"{str(row.scope).replace('_', ' ')}"
            )
            for row in summary.itertuples()
        ]

        values = summary[
            "active_mode_seasonal_index"
        ].to_numpy(float)

        colors = [
            style.MODE_COLOR.get(
                str(mode).lower(),
                style.TEAL,
            )
            for mode in summary["mode"]
        ]

        bars = ax.bar(
            labels,
            values,
            color=colors,
        )

        for bar, value in zip(
            bars,
            values,
        ):
            ax.text(
                bar.get_x()
                + bar.get_width() / 2,
                value,
                f"{value:.2f}",
                ha="center",
                va="bottom",
                fontsize=style.BAR_VALUE_FONTSIZE,
            )

        if len(values):
            ax.set_ylim(0, float(np.nanmax(values)) * 1.16)

        style.style_axis(
            ax,
            title="Modeled active-mode seasonal performance",
            ylabel="SCOPon,50 / SEERon,7 [-]",
            grid_axis="y",
        )

        save(
            fig,
            "03_standardized_SCOPon_SEERon_summary.png",
        )

    if PLOT_STAGING and not bins.empty:
        q = bins[
            (
                bins["scope"].astype(str).eq(
                    "three_HERA_plant"
                )
            )
            & (
                bins["model_status"].astype(str).eq(
                    "OK"
                )
            )
        ].copy()

        if not q.empty and "active_units" in q.columns:
            fig, ax = plt.subplots(
                figsize=(9.7, 5.5)
            )

            for mode, group in q.groupby("mode"):
                group = group.sort_values(
                    "outdoor_C"
                )

                ax.step(
                    group["outdoor_C"],
                    group["active_units"],
                    where="mid",
                    linewidth=2.2,
                    color=style.MODE_COLOR.get(
                        mode,
                        style.TEAL,
                    ),
                    label=str(mode).capitalize(),
                )

            style.style_axis(
                ax,
                title="Standardized-bin optimal active Chiller Unit count",
                xlabel="Outdoor temperature [°C]",
                ylabel="Active Chiller Units [-]",
            )

            ax.set_yticks(
                [1, 2, 3]
            )

            ax.legend(
                loc="best"
            )

            save(
                fig,
                "05_standardized_active_chiller_unit_count.png",
            )

    pass


if __name__ == "__main__":
    main()
