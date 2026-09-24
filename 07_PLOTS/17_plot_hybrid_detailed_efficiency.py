"""
17_plot_hybrid_detailed_efficiency.py

Plots the corrected same-ambient hybrid analysis.

This REPLACES the Hotfix-5 contour plotting script.

No heating-load x cooling-load contour plots are produced.
No raw measured-point scatter is overlaid.

All figures are functions of the physically common outdoor temperature.
"""

# ============================================================
# 1. IMPORTS
# ============================================================

from pathlib import Path
import importlib.util
import shutil
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

INPUT_FOLDER = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "annual"
    / "hybrid_detailed"
)

INPUT_OUTDOOR_SUMMARY = (
    INPUT_FOLDER
    / "hybrid_same_ambient_outdoor_summary.csv"
)

INPUT_OVERALL_SUMMARY = (
    INPUT_FOLDER
    / "hybrid_same_ambient_overall_summary.csv"
)

OUTPUT_FOLDER = (
    PROJECT_ROOT
    / "08_THESIS_EXPORT"
    / "figures"
    / "annual"
    / "hybrid_detailed"
)


# ============================================================
# 3. PLOT SELECTION
# ============================================================

PLOT_HYBRID_LOADS_VS_OUTDOOR = True
PLOT_EFFICIENCY_VS_OUTDOOR = True
PLOT_ELECTRICAL_POWER_VS_OUTDOOR = True
PLOT_HX_APPROACH_VS_OUTDOOR = True


# ============================================================
# 4. MODULE LOADING
# ============================================================

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


config = load_module(
    "config_plot_hybrid_same_ambient",
    CONFIG_FILE,
)

table_io = load_module(
    "table_io_plot_hybrid_same_ambient",
    TABLE_IO_FILE,
)

style = load_module(
    "style_plot_hybrid_same_ambient",
    PLOT_STYLE_FILE,
)

style.setup_plot_theme()


# ============================================================
# 5. HELPERS
# ============================================================

def read_optional(path):
    if path.exists():
        return table_io.read_table(
            path
        )

    csv_path = path.with_suffix(
        ".csv"
    )

    if csv_path.exists():
        return table_io.read_table(
            csv_path
        )

    return pd.DataFrame()


def save(fig, filename, right=0.98):
    style.save_figure(
        fig,
        OUTPUT_FOLDER / filename,
        dpi=config.PLOT_DPI,
        right=right,
    )


def save_fixed_canvas(fig, filename):
    """Save with a fixed canvas so the centered suptitle stays visually centered."""
    path = OUTPUT_FOLDER / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0.10, right=0.74, bottom=0.14, top=0.88)
    fig.savefig(
        path,
        dpi=config.PLOT_DPI,
        facecolor="white",
    )
    plt.close(fig)


def prepare(data):
    if data.empty:
        return data

    result = data.copy()

    for column in result.columns:
        if column == "Outdoor_C":
            result[
                column
            ] = pd.to_numeric(
                result[
                    column
                ],
                errors="coerce",
            )

    return result.sort_values(
        "Outdoor_C"
    )


# ============================================================
# 6. MAIN
# ============================================================

def main():
    # Delete Hotfix-5 PNGs if this plot script is run directly after replacing
    # the code but before the analysis cleanup has executed.
    if OUTPUT_FOLDER.exists():
        shutil.rmtree(
            OUTPUT_FOLDER
        )

    OUTPUT_FOLDER.mkdir(
        parents=True,
        exist_ok=True,
    )

    data = prepare(
        read_optional(
            INPUT_OUTDOOR_SUMMARY
        )
    )

    if data.empty:
        pass
        return

    x = pd.to_numeric(
        data[
            "Outdoor_C"
        ],
        errors="coerce",
    )

    # --------------------------------------------------------
    # 1. Measured simultaneous loads
    # --------------------------------------------------------

    if PLOT_HYBRID_LOADS_VS_OUTDOOR:
        fig, ax = plt.subplots(
            figsize=(9.6, 5.8)
        )

        ax.plot(
            x,
            pd.to_numeric(
                data[
                    "measured_heating_load_mean_kW"
                ],
                errors="coerce",
            ),
            marker="o",
            linewidth=2.1,
            color=style.HEATING_COLOR,
            label="Heating load",
        )

        ax.plot(
            x,
            pd.to_numeric(
                data[
                    "measured_cooling_load_mean_kW"
                ],
                errors="coerce",
            ),
            marker="o",
            linewidth=2.1,
            color=style.COOLING_COLOR,
            label="Cooling load",
        )

        style.style_axis(
            ax,
            title="Hybrid operation: simultaneous load vs outdoor temperature",
            xlabel="Outdoor temperature [°C]",
            ylabel="Mean measured thermal load [kW]",
        )

        ax.legend(
            loc="best"
        )

        save(
            fig,
            "01_hybrid_loads_vs_outdoor_temperature.png",
        )

    # --------------------------------------------------------
    # 2. Heating COP / cooling EER / combined efficiency
    # --------------------------------------------------------

    if PLOT_EFFICIENCY_VS_OUTDOOR:
        fig, ax = plt.subplots(
            figsize=(9.6, 5.8)
        )

        ax.plot(
            x,
            pd.to_numeric(
                data[
                    "heating_COP_energy_weighted"
                ],
                errors="coerce",
            ),
            marker="o",
            linewidth=2.1,
            color=style.HEATING_COLOR,
            label="Heating COP",
        )

        ax.plot(
            x,
            pd.to_numeric(
                data[
                    "cooling_EER_energy_weighted"
                ],
                errors="coerce",
            ),
            marker="o",
            linewidth=2.1,
            color=style.COOLING_COLOR,
            label="Cooling EER",
        )

        ax.plot(
            x,
            pd.to_numeric(
                data[
                    "combined_efficiency_energy_weighted"
                ],
                errors="coerce",
            ),
            marker="o",
            linewidth=2.4,
            color=style.TEAL,
            label="Combined heating + cooling",
        )

        style.style_axis(
            ax,
            title="Hybrid operation: efficiency vs outdoor temperature",
            xlabel="Outdoor temperature [°C]",
            ylabel="Efficiency [-]",
        )

        ax.legend(
            loc="best"
        )

        save(
            fig,
            "02_hybrid_efficiency_vs_outdoor_temperature.png",
        )

    # --------------------------------------------------------
    # 3. Electrical power
    # --------------------------------------------------------

    if PLOT_ELECTRICAL_POWER_VS_OUTDOOR:
        fig, ax = plt.subplots(
            figsize=(9.6, 5.8)
        )

        ax.plot(
            x,
            pd.to_numeric(
                data[
                    "mean_heating_power_kW"
                ],
                errors="coerce",
            ),
            marker="o",
            linewidth=2.0,
            color=style.HEATING_COLOR,
            label="Heating Chiller Unit power",
        )

        ax.plot(
            x,
            pd.to_numeric(
                data[
                    "mean_cooling_power_kW"
                ],
                errors="coerce",
            ),
            marker="o",
            linewidth=2.0,
            color=style.COOLING_COLOR,
            label="Cooling Chiller Unit power",
        )

        ax.plot(
            x,
            pd.to_numeric(
                data[
                    "mean_total_power_kW"
                ],
                errors="coerce",
            ),
            marker="o",
            linewidth=2.3,
            color=style.TEAL,
            label="Total Chiller Unit power",
        )

        style.style_axis(
            ax,
            title="Hybrid operation: electrical power vs outdoor temperature",
            xlabel="Outdoor temperature [°C]",
            ylabel="Mean electrical power [kW]",
        )

        ax.legend(
            loc="best"
        )

        save(
            fig,
            "03_hybrid_electrical_power_vs_outdoor_temperature.png",
        )

    # --------------------------------------------------------
    # 7. Heat-exchanger approach temperatures
    # --------------------------------------------------------

    if PLOT_HX_APPROACH_VS_OUTDOOR:
        fig, ax = plt.subplots(
            figsize=(11.4, 5.9)
        )

        ax.plot(
            x,
            pd.to_numeric(
                data[
                    "mean_heating_air_approach_K"
                ],
                errors="coerce",
            ),
            linewidth=2.0,
            color=style.HEATING_COLOR,
            label="Heating air",
        )

        ax.plot(
            x,
            pd.to_numeric(
                data[
                    "mean_heating_water_approach_K"
                ],
                errors="coerce",
            ),
            linewidth=2.0,
            linestyle="--",
            color=style.HEATING_COLOR,
            label="Heating water",
        )

        ax.plot(
            x,
            pd.to_numeric(
                data[
                    "mean_cooling_air_approach_K"
                ],
                errors="coerce",
            ),
            linewidth=2.0,
            color=style.COOLING_COLOR,
            label="Cooling air",
        )

        ax.plot(
            x,
            pd.to_numeric(
                data[
                    "mean_cooling_water_approach_K"
                ],
                errors="coerce",
            ),
            linewidth=2.0,
            linestyle="--",
            color=style.COOLING_COLOR,
            label="Cooling water",
        )

        style.style_axis(
            ax,
            xlabel="Outdoor temperature [°C]",
            ylabel="Approach temperature [K]",
        )

        # Use the full valid hybrid-data range on the x-axis.
        # Do not crop lower outdoor-temperature bins.

        ax.legend(
            loc="upper left",
            bbox_to_anchor=(
                1.01,
                1.0,
            ),
            borderaxespad=0.0,
        )

        save_fixed_canvas(
            fig,
            "04_hybrid_HX_approach_vs_outdoor_temperature.png",
        )

    pass


if __name__ == "__main__":
    main()
