"""
15_plot_mixed_unit_sizing.py

Plots the precomputed hypothetical mixed-size Chiller Unit result tables.

No fleet dispatch or thermodynamic calculation occurs in this file.
"""

# ============================================================
# 1. IMPORTS
# ============================================================

from pathlib import Path
import importlib.util
import sys

import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# 2. FILES USED BY THIS SCRIPT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONFIG_FILE = (
    PROJECT_ROOT
    / "00_CONFIG"
    / "config.py"
)

TABLE_IO_FILE = (
    PROJECT_ROOT
    / "00_CONFIG"
    / "table_io.py"
)

PLOT_STYLE_FILE = (
    PROJECT_ROOT
    / "00_CONFIG"
    / "plot_style.py"
)

INPUT_SIZE_SWEEP = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "optimization"
    / "mixed_sizing"
    / "mixed_unit_size_sweep.csv"
)

INPUT_CD_SENSITIVITY = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "optimization"
    / "mixed_sizing"
    / "mixed_unit_cycling_sensitivity.csv"
)

OUTPUT_FOLDER = (
    PROJECT_ROOT
    / "08_THESIS_EXPORT"
    / "figures"
    / "optimization"
    / "mixed_sizing"
)


# ============================================================
# 3. PLOT SELECTION
# ============================================================

PLOT_ENERGY_SAVING = True
PLOT_CYCLING_REDUCTION = True
PLOT_CD_SENSITIVITY = True
PLOT_REFERENCE_COVERAGE = False


# ============================================================
# 4. MODULE LOADING
# ============================================================

def load_module(
    name,
    path,
):
    spec = importlib.util.spec_from_file_location(
        name,
        path,
    )

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[
        name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


config = load_module(
    "config_plot_mixed",
    CONFIG_FILE,
)

table_io = load_module(
    "table_io_plot_mixed",
    TABLE_IO_FILE,
)

style = load_module(
    "style_plot_mixed",
    PLOT_STYLE_FILE,
)

style.setup_plot_theme()


# ============================================================
# 5. INPUT / SAVE HELPERS
# ============================================================

def read_optional(
    path,
):
    if path.exists():
        return table_io.read_table(
            path
        )

    csv = path.with_suffix(
        ".csv"
    )

    if csv.exists():
        return table_io.read_table(
            csv
        )

    return pd.DataFrame()


def save(
    fig,
    filename,
):
    style.save_figure(
        fig,
        OUTPUT_FOLDER / filename,
        dpi=config.PLOT_DPI,
    )


# ============================================================
# 6. MAIN
# ============================================================

def main():
    sizing = read_optional(
        INPUT_SIZE_SWEEP
    )

    sensitivity = read_optional(
        INPUT_CD_SENSITIVITY
    )

    if (
        PLOT_ENERGY_SAVING
        and not sizing.empty
    ):
        fig, ax = plt.subplots(
            figsize=(
                9.3,
                5.5,
            )
        )

        ax.plot(
            100.0
            * sizing[
                "small_unit_size_factor"
            ],
            sizing[
                "electrical_saving_percent"
            ],
            marker="o",
            linewidth=2.3,
            color=style.TEAL,
        )

        style.style_axis(
            ax,
            title=(
                "Mixed-size fleet electricity sensitivity"
            ),
            xlabel=(
                "Small-unit size [% of current Chiller Unit]"
            ),
            ylabel=(
                "Electricity saving vs reference [%]"
            ),
        )

        save(
            fig,
            "01_mixed_size_energy_saving.png",
        )

    if (
        PLOT_CYCLING_REDUCTION
        and not sizing.empty
    ):
        fig, ax = plt.subplots(
            figsize=(
                9.3,
                5.5,
            )
        )

        ax.plot(
            100.0
            * sizing[
                "small_unit_size_factor"
            ],
            sizing[
                "heating_cycling_reduction_hours"
            ],
            marker="o",
            linewidth=2.3,
            color=style.HEATING_COLOR,
            label="Heating",
        )

        ax.plot(
            100.0
            * sizing[
                "small_unit_size_factor"
            ],
            sizing[
                "cooling_cycling_reduction_hours"
            ],
            marker="o",
            linewidth=2.3,
            color=style.COOLING_COLOR,
            label="Cooling",
        )

        style.style_axis(
            ax,
            title=(
                "Cycling-exposure reduction with one smaller Chiller Unit"
            ),
            xlabel=(
                "Small-unit size [% of current Chiller Unit]"
            ),
            ylabel=(
                "Avoided cycling hours [h]"
            ),
        )

        ax.legend(
            loc="best"
        )

        save(
            fig,
            "02_mixed_size_cycling_reduction.png",
        )

    if (
        PLOT_CD_SENSITIVITY
        and not sensitivity.empty
    ):
        fig, ax = plt.subplots(
            figsize=(
                8.9,
                5.4,
            )
        )

        ax.plot(
            sensitivity[
                "cycling_degradation_coefficient"
            ],
            sensitivity[
                "electrical_saving_percent"
            ],
            marker="o",
            linewidth=2.3,
            color=style.TEAL,
        )

        style.style_axis(
            ax,
            title=(
                "Mixed-size saving sensitivity to cycling degradation"
            ),
            xlabel=(
                "Cycling degradation coefficient Cd [-]"
            ),
            ylabel=(
                "Electricity saving [%]"
            ),
        )

        save(
            fig,
            "03_mixed_size_Cd_sensitivity.png",
        )

    if (
        PLOT_REFERENCE_COVERAGE
        and not sizing.empty
    ):
        fig, ax = plt.subplots(
            figsize=(
                8.9,
                5.4,
            )
        )

        ax.plot(
            100.0
            * sizing[
                "small_unit_size_factor"
            ],
            sizing[
                "coverage_of_reference_percent"
            ],
            marker="o",
            linewidth=2.3,
            color=style.POINT_GREY,
        )

        ax.axhline(
            100.0,
            linestyle="--",
            linewidth=1.2,
            color="black",
        )

        style.style_axis(
            ax,
            title=(
                "Mixed-fleet reference-load coverage"
            ),
            xlabel=(
                "Small-unit size [% of current Chiller Unit]"
            ),
            ylabel=(
                "Reference-valid operating-hour coverage [%]"
            ),
        )

        save(
            fig,
            "04_mixed_size_reference_coverage.png",
        )

    pass


if __name__ == "__main__":
    main()
