"""
Shared thesis plotting style.

"""

# ============================================================
# 1. IMPORTS
# ============================================================

from pathlib import Path
import os
import tempfile
from typing import Optional
import numpy as np
import matplotlib.pyplot as plt


# ============================================================
# 2. COLORS
# ============================================================

BLUE = "#1565C0"
GREEN = "#00A65A"
YELLOW = "#F9C400"
TEAL = "#008C95"
RED = "#C62828"
ORANGE = "#EF6C00"
PURPLE = "#7B1FA2"
DARK = "#1F2933"
TEXT_GREY = "#59636E"
GRID_GREY = "#D9DEE5"
BORDER_GREY = "#CBD2D9"
POINT_GREY = "#303030"

# Value labels placed directly above/on bars are intentionally smaller
# than axis, tick and legend text to avoid crowding.
BAR_VALUE_FONTSIZE = 10

HEATING_COLOR = GREEN
COOLING_COLOR = BLUE

MODE_COLOR = {
    "heating": HEATING_COLOR,
    "cooling": COOLING_COLOR,
}

UNIT_COLOR = {
    1: BLUE,
    2: GREEN,
    3: YELLOW,
}


# ============================================================
# 3. GLOBAL THEME
# ============================================================

def setup_plot_theme() -> None:
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "axes.edgecolor": BORDER_GREY,
        "axes.labelcolor": DARK,
        "axes.titlecolor": DARK,
        "text.color": DARK,
        "xtick.color": DARK,
        "ytick.color": DARK,
        "font.family": "DejaVu Sans",
        "font.size": 16,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 16,
        "xtick.labelsize": 16,
        "ytick.labelsize": 16,
        "legend.fontsize": 16,
        "legend.title_fontsize": 16,
        "legend.frameon": False,
    })


def style_axis(
    ax,
    title: Optional[str] = None,
    xlabel: Optional[str] = None,
    ylabel: Optional[str] = None,
    grid_axis: str = "both",
) -> None:
    # Thesis figures use the Word caption as the figure title.
    # Keep the title argument for call compatibility, but do not render it.
    if xlabel:
        ax.set_xlabel(xlabel, labelpad=12)
    if ylabel:
        ax.set_ylabel(ylabel, labelpad=9)

    normalized_grid_axis = (
        str(grid_axis).strip().lower()
        if grid_axis is not None
        else "none"
    )

    if normalized_grid_axis in {"none", "off", "false"}:
        ax.grid(False)
    else:
        if normalized_grid_axis not in {"x", "y", "both"}:
            raise ValueError(
                "grid_axis must be one of: 'x', 'y', 'both', 'none'"
            )

        ax.grid(
            True,
            axis=normalized_grid_axis,
            color=GRID_GREY,
            linestyle="--",
            linewidth=0.7,
            alpha=0.85,
        )
    ax.set_axisbelow(True)
    ax.tick_params(pad=5, labelsize=16)

    for spine in ax.spines.values():
        spine.set_color(BORDER_GREY)
        spine.set_linewidth(1.0)


def _save_png(
    fig,
    path: Path,
    *,
    dpi: int = 220,
) -> None:
    """Save a PNG robustly on Windows/Python 3.14.

    Matplotlib ultimately hands filename paths to Pillow. On some Windows
    installations this can raise ``OSError: [Errno 22] Invalid argument`` even
    for a normal-looking final path. First try a native string path. If that
    exact error occurs, render to a short temporary PNG in the same directory
    and atomically replace the requested output file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path_str = str(path)

    try:
        fig.savefig(
            path_str,
            dpi=dpi,
            facecolor="white",
            bbox_inches="tight",
        )
        return
    except OSError as exc:
        if getattr(exc, "errno", None) != 22:
            raise

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".png",
            prefix="mpl_",
            dir=str(path.parent),
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)

        fig.savefig(
            str(temp_path),
            dpi=dpi,
            facecolor="white",
            bbox_inches="tight",
        )
        os.replace(
            str(temp_path),
            path_str,
        )
        temp_path = None
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)


def save_png(
    fig,
    path: Path,
    dpi: int = 220,
) -> None:
    """Save an already-laid-out figure without changing its margins."""
    _save_png(
        fig,
        path,
        dpi=dpi,
    )


def save_figure(
    fig,
    path: Path,
    dpi: int = 220,
    right: float = 0.98,
    bottom: float = 0.08,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=[0.0, bottom, right, 0.985])
    _save_png(
        fig,
        path,
        dpi=dpi,
    )
    plt.close(fig)


# ============================================================
# 4. HELPER UTILITIES
# ============================================================

def fixed_width_bars(
    ax,
    labels,
    values,
    *,
    width: float = 0.55,
    min_total_span: float = 4.0,
    rotation: float = 0.0,
    ha: str = 'center',
    **kwargs,
):
    """
    Draw bars with a stable visual width even when only a few categories exist.
    """
    labels = list(labels)
    values = list(values)
    x = np.arange(len(labels), dtype=float)
    bars = ax.bar(x, values, width=width, **kwargs)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=rotation, ha=ha)

    if len(x):
        center = 0.5 * (x[0] + x[-1])
        span = max(min_total_span, (len(x) - 1) + 1.4)
        ax.set_xlim(center - span / 2.0, center + span / 2.0)

    return bars, x
