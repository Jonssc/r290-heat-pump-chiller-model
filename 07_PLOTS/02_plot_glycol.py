"""
02_plot_glycol.py

Plots:
1) the final glycol-property database; and
2) the aligned-reference OE meter validation comparing the nominal 29 vol-%
   meter configuration with a 40 vol-% recalculation using the dedicated
   meter-validation density/cp tables.

The 29% comparison is retained only as a validation/reference diagnostic. The
thesis interpretation of the installed system fluid remains 40 vol-% glycol.
"""

from pathlib import Path
import importlib.util
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = PROJECT_ROOT / '00_CONFIG' / 'config.py'
TABLE_IO_FILE = PROJECT_ROOT / '00_CONFIG' / 'table_io.py'
PLOT_STYLE_FILE = PROJECT_ROOT / '00_CONFIG' / 'plot_style.py'

INPUT_PROPERTY_DATABASE = PROJECT_ROOT / '06_RESULTS' / 'databases' / 'glycol_property_database.csv'
INPUT_METER_VALIDATION_ROWS = PROJECT_ROOT / '06_RESULTS' / 'validation' / 'glycol_meter' / '01_aligned_reference_29_vs_40_rows.csv'
INPUT_METER_VALIDATION_SUMMARY = PROJECT_ROOT / '06_RESULTS' / 'validation' / 'glycol_meter' / '02_aligned_reference_29_vs_40_summary.csv'

OUTPUT_FOLDER = PROJECT_ROOT / '08_THESIS_EXPORT' / 'figures' / 'glycol'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


config = load_module('config_plot_glycol', CONFIG_FILE)
table_io = load_module('table_io_plot_glycol', TABLE_IO_FILE)
style = load_module('style_plot_glycol', PLOT_STYLE_FILE)
style.setup_plot_theme()


# Validation figure colors intentionally follow the existing thesis palette.
COLOR_29 = style.GREEN
COLOR_40 = style.YELLOW
UNIT_COLORS = {
    1: style.BLUE,
    2: style.GREEN,
    3: style.YELLOW,
}
UNIT_MARKERS = {
    1: 'o',
    2: 's',
    3: '^',
}
UNIT_LABELS = {
    1: 'HP1 heating',
    2: 'HP2 cooling',
    3: 'HP3 cooling',
}


def save(fig, filename, *, right=0.98, bottom=0.08):
    style.save_figure(
        fig,
        OUTPUT_FOLDER / filename,
        dpi=config.PLOT_DPI,
        right=right,
        bottom=bottom,
    )


def plot_property(data, column, ylabel, title, filename, exclude_concentrations=None):
    if column not in data.columns:
        return

    qdata = data.copy()
    if exclude_concentrations is not None:
        excl = set(float(x) for x in exclude_concentrations)
        conc = pd.to_numeric(qdata['concentration_vol_percent'], errors='coerce')
        qdata = qdata.loc[~conc.isin(excl)].copy()

    fig, ax = plt.subplots(figsize=(9.4, 5.6))

    for concentration, group in qdata.groupby('concentration_vol_percent'):
        q = group.sort_values('temperature_C')
        ax.plot(
            q['temperature_C'],
            pd.to_numeric(q[column], errors='coerce'),
            linewidth=2.0,
            marker='o',
            markersize=3.0,
            label=f'{float(concentration):.0f} vol-%',
        )

    style.style_axis(
        ax,
        title=title,
        xlabel='Fluid temperature [°C]',
        ylabel=ylabel,
    )

    ax.legend(
        loc='upper left',
        bbox_to_anchor=(1.01, 1.0),
        borderaxespad=0.0,
    )

    save(fig, filename, right=0.82)


# ============================================================
# ALIGNED-REFERENCE METER VALIDATION PLOTS
# ============================================================

def plot_correction_vs_temperature(rows):
    required = {
        'unit',
        'mean_fluid_temperature_C',
        'deviation_29vol_vs_logged_percent',
        'deviation_40vol_vs_logged_percent',
    }
    if rows.empty or not required.issubset(rows.columns):
        return

    fig, ax = plt.subplots(figsize=(10.4, 6.1))

    for unit, group in rows.groupby('unit'):
        unit = int(unit)
        marker = UNIT_MARKERS.get(unit, 'o')

        ax.scatter(
            group['mean_fluid_temperature_C'],
            group['deviation_29vol_vs_logged_percent'],
            s=28,
            marker=marker,
            color=COLOR_29,
            alpha=0.42,
            edgecolors='white',
            linewidths=0.35,
        )

        ax.scatter(
            group['mean_fluid_temperature_C'],
            group['deviation_40vol_vs_logged_percent'],
            s=28,
            marker=marker,
            color=COLOR_40,
            alpha=0.42,
            edgecolors='white',
            linewidths=0.35,
        )

    ax.axhline(0.0, color='black', linestyle='--', linewidth=1.4)

    style.style_axis(
        ax,
        title='29% vs 40% glycol correction vs fluid temperature',
        xlabel='Mean fluid temperature [°C]',
        ylabel='(Recalculated − Logged) / Logged [%]',
    )

    # Extra vertical headroom keeps the upper-left legend clear of the
    # 29% data cloud without shrinking the thesis font sizes.
    y_low, y_high = ax.get_ylim()
    ax.set_ylim(y_low, y_high + 0.75)

    series_handles = [
        Line2D([0], [0], marker='o', linestyle='none', markerfacecolor=COLOR_29,
               markeredgecolor='none', markersize=7, label='29%'),
        Line2D([0], [0], marker='o', linestyle='none', markerfacecolor=COLOR_40,
               markeredgecolor='none', markersize=7, label='40%'),
        Line2D([0], [0], color='black', linestyle='--', linewidth=1.4,
               label='Logged Data'),
    ]

    unit_handles = [
        Line2D([0], [0], marker=UNIT_MARKERS[u], linestyle='none',
               markerfacecolor=style.POINT_GREY, markeredgecolor='none',
               markersize=7, label=UNIT_LABELS[u])
        for u in (1, 2, 3)
    ]

    legend1 = ax.legend(
        handles=series_handles,
        loc='upper left',
        bbox_to_anchor=(0.02, 0.99),
        frameon=False,
    )
    ax.add_artist(legend1)

    ax.legend(
        handles=unit_handles,
        title='Units',
        loc='lower right',
        frameon=False,
    )

    save(fig, '06_aligned_reference_29_vs_40_correction_vs_temperature.png')


def plot_mean_deviation(summary):
    required = {
        'unit',
        'mean_deviation_29vol_vs_logged_percent',
        'mean_deviation_40vol_vs_logged_percent',
    }
    if summary.empty or not required.issubset(summary.columns):
        return

    summary = summary.sort_values('unit').copy()
    units = summary['unit'].astype(int).tolist()
    labels = [UNIT_LABELS.get(u, f'HP{u}') for u in units]

    x = np.arange(len(summary), dtype=float)
    width = 0.24

    v29 = summary['mean_deviation_29vol_vs_logged_percent'].to_numpy(float)
    v40 = summary['mean_deviation_40vol_vs_logged_percent'].to_numpy(float)

    fig, ax = plt.subplots(figsize=(11.5, 7.0))

    b29 = ax.bar(
        x - width / 2.0,
        v29,
        width=width,
        color=COLOR_29,
        label='29% vs Logged Data',
    )
    b40 = ax.bar(
        x + width / 2.0,
        v40,
        width=width,
        color=COLOR_40,
        label='40% vs Logged Data',
    )

    ax.axhline(0.0, color='black', linestyle='--', linewidth=1.3)

    style.style_axis(
        ax,
        title='Glycol correction: deviation from Logged Data',
        ylabel='Mean deviation [%]',
        grid_axis='y',
    )

    ax.set_xticks(x)
    ax.set_xticklabels([label.replace(' ', '\n', 1) for label in labels])
    ax.set_ylim(
        min(float(np.nanmin(v40)) - 0.35, -0.5),
        max(float(np.nanmax(v29)) + 0.65, 0.5),
    )

    for bars in (b29, b40):
        for bar in bars:
            value = float(bar.get_height())
            xtext = bar.get_x() + bar.get_width() / 2.0
            offset = 0.10 if value >= 0 else -0.10
            ax.text(
                xtext,
                value + offset,
                f'{value:+.1f}%',
                ha='center',
                va='bottom' if value >= 0 else 'top',
                color=style.TEXT_GREY,
                fontsize=style.BAR_VALUE_FONTSIZE,
            )

    ax.legend(
        loc='upper center',
        bbox_to_anchor=(0.5, -0.24),
        ncol=2,
        frameon=False,
    )

    save(
        fig,
        '07_aligned_reference_mean_deviation_29_vs_40.png',
        bottom=0.30,
    )


def plot_recalculated_vs_logged(rows, concentration):
    logged_col = 'logged_thermal_power_kW'
    recalculated_col = f'recalculated_{concentration}vol_thermal_power_kW'

    if rows.empty or recalculated_col not in rows.columns:
        return

    q = rows.dropna(subset=[logged_col, recalculated_col]).copy()
    if q.empty:
        return

    fig, ax = plt.subplots(figsize=(8.2, 7.0))

    lo = max(0.0, min(q[logged_col].min(), q[recalculated_col].min()) * 0.95)
    hi = max(q[logged_col].max(), q[recalculated_col].max()) * 1.04

    for unit, group in q.groupby('unit'):
        unit = int(unit)
        ax.scatter(
            group[logged_col],
            group[recalculated_col],
            s=24,
            alpha=0.45,
            color=UNIT_COLORS.get(unit, style.POINT_GREY),
            marker='o',
            edgecolors='white',
            linewidths=0.35,
            label=UNIT_LABELS.get(unit, f'HP{unit}'),
        )

    ax.plot(
        [lo, hi],
        [lo, hi],
        color='black',
        linestyle='--',
        linewidth=1.4,
        label='1:1',
    )

    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect('equal', adjustable='box')

    style.style_axis(
        ax,
        title=f'{concentration}% glycol vs Logged Data',
        xlabel='Logged thermal power [kW]',
        ylabel=f'Recalculated {concentration}% glycol thermal power [kW]',
    )

    ax.legend(loc='upper left', frameon=False)

    save(
        fig,
        f'{8 if concentration == 29 else 9:02d}_aligned_reference_{concentration}pct_vs_logged_power.png',
    )


def plot_meter_validation():
    if not table_io.table_exists(INPUT_METER_VALIDATION_ROWS):
        return
    if not table_io.table_exists(INPUT_METER_VALIDATION_SUMMARY):
        return

    rows = table_io.read_table(INPUT_METER_VALIDATION_ROWS)
    summary = table_io.read_table(INPUT_METER_VALIDATION_SUMMARY)

    plot_correction_vs_temperature(rows)
    plot_mean_deviation(summary)
    plot_recalculated_vs_logged(rows, 29)
    plot_recalculated_vs_logged(rows, 40)


# ============================================================
# MAIN
# ============================================================

def main():
    if table_io.table_exists(INPUT_PROPERTY_DATABASE):
        data = table_io.read_table(INPUT_PROPERTY_DATABASE)

        plot_property(data, 'density_kg_m3', 'Density [kg/m³]', 'DOWCAL 200E density', '01_density_vs_temperature.png')
        plot_property(data, 'cp_kJ_kgK', 'Specific heat capacity [kJ/(kg·K)]', 'DOWCAL 200E specific heat capacity', '02_cp_vs_temperature.png')

        # The normalized database currently uses dynamic_viscosity_mPas.
        viscosity_col = (
            'dynamic_viscosity_mPa_s'
            if 'dynamic_viscosity_mPa_s' in data.columns
            else 'dynamic_viscosity_mPas'
        )
        plot_property(data, viscosity_col, 'Dynamic viscosity [mPa·s]', 'DOWCAL 200E dynamic viscosity', '03_viscosity_vs_temperature.png', exclude_concentrations=[0])

        plot_property(data, 'thermal_conductivity_W_mK', 'Thermal conductivity [W/(m·K)]', 'DOWCAL 200E thermal conductivity', '04_thermal_conductivity_vs_temperature.png', exclude_concentrations=[0])
        plot_property(data, 'volumetric_heat_capacity_kJ_m3K', 'Volumetric heat capacity [kJ/(m³·K)]', 'DOWCAL 200E volumetric heat capacity', '05_volumetric_heat_capacity.png', exclude_concentrations=[0])

    plot_meter_validation()

    pass


if __name__ == '__main__':
    main()
