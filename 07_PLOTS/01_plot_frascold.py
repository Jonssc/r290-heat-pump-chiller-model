"""
01_plot_frascold.py

Creates Frascold figures ONLY from the already-generated master CSV database.

The compressor model is NOT recalculated here.

To use a different database or output folder later, change the file paths in
Section 2 at the top of this file.

To choose which figures are generated, change the True/False switches in
Section 3.
"""

# ============================================================
# 1. IMPORTS
# ============================================================

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm


# ============================================================
# 2. FILES USED BY THIS SCRIPT
#    CHANGE THESE PATHS HERE IF A DIFFERENT FILE IS USED
# ============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

CONFIG_FILE = (
    PROJECT_ROOT
    / "00_CONFIG"
    / "config.py"
)

INPUT_FRASCOLD_DATABASE = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "databases"
    / "frascold_performance_grid.csv"
)

OUTPUT_PLOT_FOLDER = (
    PROJECT_ROOT
    / "08_THESIS_EXPORT"
    / "figures"
    / "frascold"
)


# ============================================================
# 3. PLOT SELECTION
#    TRUE = CREATE PLOT
#    FALSE = SKIP PLOT
# ============================================================

PLOT_HEATING_COP_VS_FREQUENCY = True

PLOT_COOLING_EER_VS_FREQUENCY = True

PLOT_HEATING_COP_CONTOUR = True

PLOT_COOLING_EER_CONTOUR = True



# ============================================================
# 4. PLOT-SPECIFIC CHANGEABLE VARIABLES
# ============================================================

# Frequency-line figures:
LINE_T_EVAP_C = -5.0
LINE_T_COND_C = 45.0

# Contour figures:
CONTOUR_FREQUENCY_HZ = 50.0

# Contour-display settings:
#
# Filled bands cover the COMPLETE valid Frascold performance range at the
# selected frequency. Valid low/high COP/EER values are therefore never left
# white simply because they fall outside a manually chosen scale.
CONTOUR_FILLED_STEP = 0.5

# Black isolines are intentionally less dense than the color bands.
CONTOUR_LINE_STEP = 1.0

# Conservative plot-only fill of small invalid Frascold edge cells.
# This removes the white/grey corner artifacts in the final contour figures
# without changing the saved master database. The extrapolation is limited to
# cells that remain inside the plausible compressor-map envelope.
FILL_INVALID_EDGE_CELLS = True
MAX_EDGE_EXTRAPOLATION_COLS = 5
MAX_EDGE_EXTRAPOLATION_ROWS = 10
FILL_ITERATIONS = 3


# ============================================================
# 5. LOAD CONFIG
# ============================================================

from importlib.util import (
    module_from_spec,
    spec_from_file_location,
)


def load_module(
    module_name,
    file_path,
):
    spec = spec_from_file_location(
        module_name,
        file_path,
    )

    module = module_from_spec(
        spec
    )

    spec.loader.exec_module(
        module
    )

    return module


config = load_module(
    "thesis_config_plot",
    CONFIG_FILE,
)


# ============================================================
# 6. VISUAL STYLE
# ============================================================

HEATING_COLOR = "#00A65A"
COOLING_COLOR = "#1565C0"
POINT_COLOR = "#303030"
GRID_COLOR = "#D0D0D0"
TEXT_COLOR = "#222222"

plt.rcParams.update({
    "figure.facecolor":
        "white",

    "axes.facecolor":
        "white",

    "savefig.facecolor":
        "white",

    "font.family":
        "DejaVu Sans",

    "font.size":
        16,

    "axes.titlesize":
        14,

    "axes.titleweight":
        "bold",

    "axes.labelsize":
        16,

    "axes.labelcolor":
        TEXT_COLOR,

    "xtick.color":
        TEXT_COLOR,

    "ytick.color":
        TEXT_COLOR,

    "xtick.labelsize":
        16,

    "ytick.labelsize":
        16,

    "legend.fontsize":
        16,

    "legend.title_fontsize":
        16,
})


def style_axis(
    ax,
    grid_axis="both",
):
    ax.grid(
        True,
        axis=grid_axis,
        linestyle="--",
        linewidth=0.8,
        color=GRID_COLOR,
        alpha=0.72,
        zorder=0,
    )

    ax.set_axisbelow(
        True
    )


def save_figure(
    fig,
    filename,
):
    OUTPUT_PLOT_FOLDER.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = (
        OUTPUT_PLOT_FOLDER
        / filename
    )

    fig.tight_layout()

    fig.savefig(
        output,
        dpi=config.PLOT_DPI,
        bbox_inches="tight",
    )

    plt.close(
        fig
    )

    print(
        f"Created: {output}"
    )


# ============================================================
# 7. LOAD RESULT DATABASE
# ============================================================

def load_database():
    if not INPUT_FRASCOLD_DATABASE.exists():
        raise FileNotFoundError(
            "Frascold master database not found:\n"
            f"{INPUT_FRASCOLD_DATABASE}\n\n"
            "Run 04_GENERATE_DATABASES/"
            "01_generate_frascold_grid.py first."
        )

    first_line = (
        INPUT_FRASCOLD_DATABASE
        .read_text(
            encoding="utf-8-sig",
            errors="replace",
        )
        .splitlines()[0]
    )

    if first_line.count(";") > first_line.count(","):
        data = pd.read_csv(
            INPUT_FRASCOLD_DATABASE,
            sep=";",
            decimal=",",
        )
    else:
        data = pd.read_csv(
            INPUT_FRASCOLD_DATABASE,
            sep=",",
            decimal=".",
        )

    return data[
        data[
            "model_status"
        ].astype(str)
        == "OK"
    ].copy()


# ============================================================
# 8. DATA FILTER HELPERS
# ============================================================

def exact_filter(
    data,
    column,
    value,
):
    mask = np.isclose(
        data[
            column
        ].to_numpy(
            dtype=float
        ),
        float(
            value
        ),
        atol=1e-9,
        rtol=0,
    )

    filtered = data[
        mask
    ].copy()

    if filtered.empty:
        available = np.sort(
            data[
                column
            ]
            .dropna()
            .unique()
        )

        raise ValueError(
            f"{column}={value} is not present "
            "in the generated database.\n"
            "Change the plot setting or regenerate "
            "the master grid with a matching increment.\n"
            f"Available range: {available.min()} "
            f"to {available.max()}"
        )

    return filtered


# ============================================================
# 9. FREQUENCY-LINE PLOTS
# ============================================================

def line_data(
    data,
):
    result = exact_filter(
        data,
        "T_evap_C",
        LINE_T_EVAP_C,
    )

    result = exact_filter(
        result,
        "T_cond_C",
        LINE_T_COND_C,
    )

    return result.sort_values(
        "frequency_Hz"
    )


def plot_heating_COP_vs_frequency(
    data,
):
    q = line_data(
        data
    )

    fig, ax = plt.subplots(
        figsize=(
            9.8,
            6.0,
        )
    )

    ax.plot(
        q[
            "frequency_Hz"
        ],
        q[
            "heating_COP"
        ],
        marker="o",
        markersize=5.2,
        linewidth=3.0,
        color=HEATING_COLOR,
    )

    ax.set_xlabel(
        "Compressor frequency [Hz]"
    )

    ax.set_ylabel(
        "Heating COP [-]"
    )

    style_axis(
        ax
    )

    save_figure(
        fig,
        "01_heating_COP_vs_frequency.png",
    )


def plot_cooling_EER_vs_frequency(
    data,
):
    q = line_data(
        data
    )

    fig, ax = plt.subplots(
        figsize=(
            9.8,
            6.0,
        )
    )

    ax.plot(
        q[
            "frequency_Hz"
        ],
        q[
            "cooling_EER"
        ],
        marker="o",
        markersize=5.2,
        linewidth=3.0,
        color=COOLING_COLOR,
    )

    ax.set_xlabel(
        "Compressor frequency [Hz]"
    )

    ax.set_ylabel(
        "Cooling EER [-]"
    )

    style_axis(
        ax
    )

    save_figure(
        fig,
        "02_cooling_EER_vs_frequency.png",
    )


def contour_data(
    data,
    metric,
):
    q = exact_filter(
        data,
        "frequency_Hz",
        CONTOUR_FREQUENCY_HZ,
    )

    pivot = q.pivot(
        index="T_cond_C",
        columns="T_evap_C",
        values=metric,
    )

    x = pivot.columns.to_numpy(
        dtype=float
    )

    y = pivot.index.to_numpy(
        dtype=float
    )

    z = pivot.to_numpy(
        dtype=float
    )

    z = conservatively_fill_invalid_edge_cells(
        z
    )

    X, Y = np.meshgrid(
        x,
        y,
    )

    return (
        X,
        Y,
        z,
    )


def nice_floor(
    value,
    step,
):
    return (
        np.floor(
            float(value)
            / float(step)
        )
        * float(step)
    )


def nice_ceil(
    value,
    step,
):
    return (
        np.ceil(
            float(value)
            / float(step)
        )
        * float(step)
    )


def edge_fill_candidate_mask(
    Z,
):
    valid = np.isfinite(
        Z
    )

    rows, cols = valid.shape
    candidate = np.zeros_like(
        valid,
        dtype=bool,
    )

    for row in range(
        rows
    ):
        left_seen = np.cumsum(
            valid[row, :]
        ) > 0

        for col in range(
            cols
        ):
            if valid[
                row,
                col,
            ]:
                continue

            if not left_seen[
                col
            ]:
                continue

            if not np.any(
                valid[
                    row + 1 :,
                    col,
                ]
            ):
                continue

            candidate[
                row,
                col,
            ] = True

    return candidate


def row_edge_estimate(
    Z,
    row,
    col,
):
    finite_cols = np.where(
        np.isfinite(
            Z[
                row,
                :col,
            ]
        )
    )[0]

    if finite_cols.size < 2:
        return None

    last_col = finite_cols[-1]
    prev_col = finite_cols[-2]

    gap = col - last_col
    if gap > MAX_EDGE_EXTRAPOLATION_COLS:
        return None

    last_val = Z[
        row,
        last_col,
    ]
    prev_val = Z[
        row,
        prev_col,
    ]

    slope = (
        last_val - prev_val
    ) / (
        last_col - prev_col
    )

    return last_val + slope * gap


def column_edge_estimate(
    Z,
    row,
    col,
):
    finite_rows = np.where(
        np.isfinite(
            Z[
                row + 1 :,
                col,
            ]
        )
    )[0]

    if finite_rows.size < 2:
        return None

    first_row = finite_rows[0] + row + 1
    second_row = finite_rows[1] + row + 1

    gap = first_row - row
    if gap > MAX_EDGE_EXTRAPOLATION_ROWS:
        return None

    first_val = Z[
        first_row,
        col,
    ]
    second_val = Z[
        second_row,
        col,
    ]

    slope = (
        second_val - first_val
    ) / (
        second_row - first_row
    )

    return first_val - slope * gap


def conservatively_fill_invalid_edge_cells(
    Z,
):
    if not FILL_INVALID_EDGE_CELLS:
        return Z

    filled = np.array(
        Z,
        dtype=float,
        copy=True,
    )

    candidate = edge_fill_candidate_mask(
        filled
    )

    if not np.any(
        candidate
    ):
        return filled

    for _ in range(
        FILL_ITERATIONS
    ):
        changed = False

        for row, col in np.argwhere(
            candidate & ~np.isfinite(
                filled
            )
        ):
            estimates = []

            row_est = row_edge_estimate(
                filled,
                row,
                col,
            )
            if row_est is not None:
                estimates.append(
                    row_est
                )

            col_est = column_edge_estimate(
                filled,
                row,
                col,
            )
            if col_est is not None:
                estimates.append(
                    col_est
                )

            if not estimates:
                continue

            filled[
                row,
                col,
            ] = float(
                np.mean(
                    estimates
                )
            )
            changed = True

        if not changed:
            break

    return filled


def complete_contour_levels(
    Z,
):
    finite = np.asarray(
        Z,
        dtype=float,
    )

    finite = finite[
        np.isfinite(
            finite
        )
    ]

    if finite.size == 0:
        raise ValueError(
            "No finite values available for contour plot."
        )

    minimum = nice_floor(
        finite.min(),
        CONTOUR_LINE_STEP,
    )

    maximum = nice_ceil(
        finite.max(),
        CONTOUR_LINE_STEP,
    )

    if np.isclose(
        minimum,
        maximum,
    ):
        maximum = (
            minimum
            + CONTOUR_LINE_STEP
        )

    contour_levels = np.arange(
        minimum,
        maximum
        + 0.5
        * CONTOUR_LINE_STEP,
        CONTOUR_LINE_STEP,
    )

    return contour_levels


def create_contour(
    data,
    metric,
    title,
    colorbar_label,
    filename,
):
    X, Y, Z = contour_data(
        data,
        metric,
    )

    contour_levels = complete_contour_levels(
        Z
    )

    masked_Z = np.ma.masked_invalid(
        Z
    )

    fig, ax = plt.subplots(
        figsize=(
            10.2,
            6.5,
        )
    )

    ax.set_facecolor(
        "white"
    )

    norm = BoundaryNorm(
        contour_levels,
        ncolors=256,
        clip=True,
    )

    filled = ax.contourf(
        X,
        Y,
        masked_Z,
        levels=contour_levels,
        norm=norm,
        extend="neither",
        corner_mask=False,
    )

    lines = ax.contour(
        X,
        Y,
        masked_Z,
        levels=contour_levels,
        linewidths=0.9,
        colors="black",
        corner_mask=False,
    )

    ax.clabel(
        lines,
        inline=True,
        fontsize=8.5,
        fmt="%.0f",
    )

    colorbar = fig.colorbar(
        filled,
        ax=ax,
        ticks=contour_levels,
        extend="neither",
    )

    colorbar.set_label(
        colorbar_label
    )

    colorbar.ax.yaxis.set_major_formatter(
        plt.FuncFormatter(
            lambda value, position:
            f"{value:.1f}"
        )
    )

    ax.set_xlabel(
        "Evaporating saturation temperature [°C]"
    )

    ax.set_ylabel(
        "Condensing saturation temperature [°C]"
    )

    style_axis(
        ax
    )

    save_figure(
        fig,
        filename,
    )



def plot_heating_COP_contour(
    data,
):
    create_contour(
        data=data,
        metric="heating_COP",
        title=(
            "Heating COP Map at "
            f"{CONTOUR_FREQUENCY_HZ:g} Hz"
        ),
        colorbar_label="Heating COP [-]",
        filename="03_heating_COP_contour.png",
    )


def plot_cooling_EER_contour(
    data,
):
    create_contour(
        data=data,
        metric="cooling_EER",
        title=(
            "Cooling EER Map at "
            f"{CONTOUR_FREQUENCY_HZ:g} Hz"
        ),
        colorbar_label="Cooling EER [-]",
        filename="04_cooling_EER_contour.png",
    )


# ============================================================
# 11. MAIN / PLOT SELECTION
# ============================================================

def main():
    data = load_database()

    if PLOT_HEATING_COP_VS_FREQUENCY:
        plot_heating_COP_vs_frequency(
            data
        )

    if PLOT_COOLING_EER_VS_FREQUENCY:
        plot_cooling_EER_vs_frequency(
            data
        )

    if PLOT_HEATING_COP_CONTOUR:
        plot_heating_COP_contour(
            data
        )

    if PLOT_COOLING_EER_CONTOUR:
        plot_cooling_EER_contour(
            data
        )


    print()
    print(
        "Selected Frascold plots finished."
    )


if __name__ == "__main__":
    main()
