"""
06_plot_circuit_and_plant_dispatch.py

Plots circuit staging and 1/2/3 Chiller Unit dispatch from precomputed result tables.
The thermodynamic model is not run in this file.

Added in Hotfix 7
-----------------
- missing 1 vs 2 vs 3 active-unit comparison curves;
- consistent plot layout and titles;
- optional chiller-only and with-unit-pump visual families;
- consistent line styling for dispatch comparison curves.
"""

from pathlib import Path
import importlib.util
import sys

import pandas as pd
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = PROJECT_ROOT / "00_CONFIG" / "config.py"
TABLE_IO_FILE = PROJECT_ROOT / "00_CONFIG" / "table_io.py"
PLOT_STYLE_FILE = PROJECT_ROOT / "00_CONFIG" / "plot_style.py"
INPUT_FOLDER = PROJECT_ROOT / "06_RESULTS" / "optimization" / "dispatch"
OUTPUT_FOLDER = PROJECT_ROOT / "08_THESIS_EXPORT" / "figures" / "optimization" / "dispatch"

PLOT_ONE_VS_TWO_CIRCUIT_POWER = True
PLOT_ONE_VS_TWO_CIRCUIT_EFFICIENCY = True
PLOT_SECOND_CIRCUIT_STRATEGY = False
PLOT_PLANT_EFFICIENCY = False
PLOT_ACTIVE_HERA_COUNT = False
PLOT_ACTIVE_UNIT_COMPARISON_CURVES = True
PLOT_SELECTED_ENVELOPE_CROSSOVER = True

BOUNDARY_TO_PLOT = "chiller_only"
PLOT_ADDITIONAL_BOUNDARIES = True
COMMON_FIGSIZE = (10.2, 5.9)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

config = load_module("config_plot_dispatch", CONFIG_FILE)
table_io = load_module("table_io_plot_dispatch", TABLE_IO_FILE)
style = load_module("style_plot_dispatch", PLOT_STYLE_FILE)
style.setup_plot_theme()


def read_table(stem):
    xlsx = INPUT_FOLDER / f"{stem}.xlsx"
    csv = INPUT_FOLDER / f"{stem}.csv"
    if xlsx.exists():
        return table_io.read_table(xlsx)
    if csv.exists():
        return table_io.read_table(csv)
    return pd.DataFrame()


def save(fig, filename, right=0.98):
    style.save_figure(fig, OUTPUT_FOLDER / filename, dpi=config.PLOT_DPI, right=right)


def style_axis_centered(fig, ax, title, xlabel, ylabel):
    # Use the axes title rather than a figure-level suptitle.  This keeps the
    # caption centered over the actual plot box even when the legend is outside
    # the axes on the right.
    style.style_axis(
        ax,
        title=title,
        xlabel=xlabel,
        ylabel=ylabel,
    )


def _unit_power_label(boundary):
    return 'Plant electrical power [kW]'


def _eff_label(mode):
    return 'Plant COP [-]' if mode == 'heating' else 'Plant EER [-]'


def _boundary_suffix(boundary):
    return 'with pumps' if boundary == 'with_unit_pump_screening' else 'chiller only'


def _boundary_file_suffix(boundary):
    return 'with_unit_pump' if boundary == 'with_unit_pump_screening' else 'chiller_only'


def _mode_color(mode):
    return style.MODE_COLOR[mode]


def plot_circuit_comparison(mode):
    data = read_table(f"01_{mode}_one_vs_two_circuits_{BOUNDARY_TO_PLOT}")
    if data.empty:
        return
    colors = {1: style.BLUE, 2: style.GREEN}
    labels = {1: '1 active circuit', 2: '2 active circuits'}

    if PLOT_ONE_VS_TWO_CIRCUIT_POWER:
        fig, ax = plt.subplots(figsize=COMMON_FIGSIZE)
        for n in (1, 2):
            q = data[data['active_circuits'] == n].sort_values('unit_load_kW')
            if q.empty:
                continue
            ax.plot(q['unit_load_kW'], q['unit_total_power_kW'], marker='o', markersize=3.5, linewidth=2.0, color=colors[n], label=labels[n])
        style_axis_centered(fig, ax, title=f"{mode.capitalize()}: 1 vs 2 active circuits — power", xlabel='Required Chiller Unit load [kW]', ylabel='Chiller Unit electrical power [kW]')
        ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1.0), borderaxespad=0.0)
        save(fig, f"01_{mode}_one_vs_two_circuit_power.png", right=0.80)

    if PLOT_ONE_VS_TWO_CIRCUIT_EFFICIENCY:
        fig, ax = plt.subplots(figsize=COMMON_FIGSIZE)
        for n in (1, 2):
            q = data[data['active_circuits'] == n].sort_values('unit_load_kW')
            if q.empty:
                continue
            ax.plot(q['unit_load_kW'], q['unit_COP_or_EER'], marker='o', markersize=3.5, linewidth=2.0, color=colors[n], label=labels[n])
        style_axis_centered(fig, ax, title=f"{mode.capitalize()}: 1 vs 2 active circuits — efficiency", xlabel='Required Chiller Unit load [kW]', ylabel='Chiller Unit COP / EER [-]')
        ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1.0), borderaxespad=0.0)
        save(fig, f"02_{mode}_one_vs_two_circuit_efficiency.png", right=0.80)


def plot_strategy(mode):
    if not PLOT_SECOND_CIRCUIT_STRATEGY:
        return
    delayed = read_table(f"03_{mode}_second_circuit_delayed_reference_{BOUNDARY_TO_PLOT}")
    efficient = read_table(f"04_{mode}_second_circuit_efficiency_strategy_{BOUNDARY_TO_PLOT}")
    if delayed.empty or efficient.empty:
        return
    fig, ax = plt.subplots(figsize=COMMON_FIGSIZE)
    ax.plot(delayed['unit_load_kW'], delayed['unit_COP_or_EER'], marker='o', markersize=3.5, linewidth=2.2, color=style.YELLOW, label='Delayed / capacity-limited reference')
    ax.plot(efficient['unit_load_kW'], efficient['unit_COP_or_EER'], marker='o', markersize=3.5, linewidth=2.4, color=style.TEAL, label='Efficiency-based second-circuit switch')
    style_axis_centered(fig, ax, title=f"{mode.capitalize()}: second-circuit activation strategy", xlabel='Required Chiller Unit load [kW]', ylabel='Chiller Unit COP / EER [-]')
    ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1.0), borderaxespad=0.0)
    save(fig, f"03_{mode}_second_circuit_strategy.png", right=0.72)


def plot_plant_dispatch(mode):
    data = read_table(f"06_{mode}_one_two_three_HERA_dispatch_{BOUNDARY_TO_PLOT}")
    if data.empty:
        return
    data = data.sort_values('total_load_kW')
    if PLOT_PLANT_EFFICIENCY:
        fig, ax = plt.subplots(figsize=COMMON_FIGSIZE)
        ax.plot(data['total_load_kW'], data['plant_COP_or_EER'], linewidth=2.3, color=_mode_color(mode))
        style_axis_centered(fig, ax, title=f"{mode.capitalize()}: optimized 1/2/3 Chiller Unit dispatch", xlabel='Total plant thermal load [kW]', ylabel='Plant COP / EER [-]')
        save(fig, f"04_{mode}_plant_dispatch_efficiency.png")
    if PLOT_ACTIVE_HERA_COUNT:
        fig, ax = plt.subplots(figsize=(10.2, 5.5))
        ax.step(data['total_load_kW'], data['optimal_active_units'], where='mid', linewidth=2.4, color=_mode_color(mode))
        style_axis_centered(fig, ax, title=f"{mode.capitalize()}: optimal active Chiller Unit count", xlabel='Total plant thermal load [kW]', ylabel='Active Chiller Units [-]')
        ax.set_yticks([1, 2, 3])
        save(fig, f"05_{mode}_optimal_active_chiller_unit_count.png")


def _build_active_unit_curves(mode, boundary):
    """Read exact-N optimized plant-dispatch curves generated by analysis.

    Important: these are no longer produced by horizontally scaling the best
    one-unit curve.  Each exact-N table contains the minimum-power load split
    between exactly N active physical Chiller Units.
    """
    curves = {}

    for units in (1, 2, 3):
        data = read_table(
            f"{6+units:02d}_{mode}_exact_{units}_active_units_{boundary}"
        )
        if data.empty:
            continue

        q = data.copy().sort_values('total_load_kW')
        q['plant_load_kW'] = pd.to_numeric(
            q['total_load_kW'], errors='coerce'
        )
        q['plant_power_kW'] = pd.to_numeric(
            q['plant_power_kW'], errors='coerce'
        )
        q['plant_COP_or_EER'] = pd.to_numeric(
            q['plant_COP_or_EER'], errors='coerce'
        )
        q['active_units'] = units

        curves[units] = q[
            [
                'plant_load_kW',
                'plant_power_kW',
                'plant_COP_or_EER',
                'active_units',
            ]
        ].dropna()

    return curves


def _read_selected_envelope(mode, boundary):
    data = read_table(
        f"06_{mode}_one_two_three_HERA_dispatch_{boundary}"
    )
    if data.empty:
        return pd.DataFrame()

    q = data.copy().sort_values('total_load_kW')
    q['plant_load_kW'] = pd.to_numeric(
        q['total_load_kW'], errors='coerce'
    )
    q['plant_power_kW'] = pd.to_numeric(
        q['plant_power_kW'], errors='coerce'
    )
    q['plant_COP_or_EER'] = pd.to_numeric(
        q['plant_COP_or_EER'], errors='coerce'
    )
    q['active_units'] = pd.to_numeric(
        q['optimal_active_units'], errors='coerce'
    )

    return q.dropna(
        subset=[
            'plant_load_kW',
            'plant_power_kW',
            'plant_COP_or_EER',
            'active_units',
        ]
    )


def _read_crossover_summary(mode, boundary):
    data = read_table(
        f"11_{mode}_exact_unit_crossover_summary_{boundary}"
    )
    if data.empty:
        return pd.DataFrame()

    q = data.copy()
    q['challenger_active_units'] = pd.to_numeric(
        q['challenger_active_units'], errors='coerce'
    )
    q['crossover_load_kW'] = pd.to_numeric(
        q['crossover_load_kW'], errors='coerce'
    )
    return q.dropna(
        subset=['challenger_active_units', 'crossover_load_kW']
    )


def _plot_exact_curves(ax, curves, value_column, colors):
    for units in (1, 2, 3):
        q = curves.get(units, pd.DataFrame())
        if q.empty:
            continue
        ax.plot(
            q['plant_load_kW'],
            q[value_column],
            marker='o',
            markersize=2.8,
            linewidth=2.0,
            color=colors[units],
            label=f'{units} active unit' + ('s' if units > 1 else ''),
        )


def _add_crossover_lines(ax, crossover):
    if crossover.empty:
        return

    line_styles = {2: '--', 3: '-.'}

    for _, row in crossover.sort_values('challenger_active_units').iterrows():
        units = int(row['challenger_active_units'])
        load = float(row['crossover_load_kW'])
        ax.axvline(
            load,
            color='black',
            linestyle=line_styles.get(units, '--'),
            linewidth=1.1,
            alpha=0.85,
            label=f'{units} Units Start',
        )


def plot_active_unit_comparison_curves(mode, boundary):
    if not PLOT_ACTIVE_UNIT_COMPARISON_CURVES:
        return

    curves = _build_active_unit_curves(mode, boundary)
    if not curves:
        pass
        return

    title_suffix = _boundary_suffix(boundary)
    colors = {1: style.BLUE, 2: style.GREEN, 3: style.YELLOW}

    # 03: Exact-N efficiency curves only. No crossover lines are drawn here so
    # the basic comparison remains clean.
    fig, ax = plt.subplots(figsize=(10.4, 5.9))
    _plot_exact_curves(
        ax,
        curves,
        'plant_COP_or_EER',
        colors,
    )
    style_axis_centered(
        fig,
        ax,
        title=(
            f"{mode.capitalize()}: 1/2/3-unit efficiency ({title_suffix})"
        ),
        xlabel='Required plant load [kW]',
        ylabel=_eff_label(mode),
    )
    ax.legend(
        loc='upper left',
        bbox_to_anchor=(1.01, 1.0),
        borderaxespad=0.0,
    )
    save(
        fig,
        f"03_{mode}_efficiency_1_vs_2_vs_3_active_units_"
        f"{_boundary_file_suffix(boundary)}.png",
        right=0.80,
    )

    # 04: Exact-N electrical-power curves only.
    fig, ax = plt.subplots(figsize=(10.4, 5.9))
    _plot_exact_curves(
        ax,
        curves,
        'plant_power_kW',
        colors,
    )
    style_axis_centered(
        fig,
        ax,
        title=(
            f"{mode.capitalize()}: 1/2/3-unit power ({title_suffix})"
        ),
        xlabel='Required plant load [kW]',
        ylabel=_unit_power_label(boundary),
    )
    ax.legend(
        loc='upper left',
        bbox_to_anchor=(1.01, 1.0),
        borderaxespad=0.0,
    )
    save(
        fig,
        f"04_{mode}_power_1_vs_2_vs_3_active_units_"
        f"{_boundary_file_suffix(boundary)}.png",
        right=0.80,
    )

    if not PLOT_SELECTED_ENVELOPE_CROSSOVER:
        return

    envelope = _read_selected_envelope(mode, boundary)
    crossover = _read_crossover_summary(mode, boundary)

    if envelope.empty:
        return

    # 05: Extra efficiency figure with selected best envelope and the calculated
    # 1->2 / 2->3 crossover loads. The original clean comparison above remains.
    fig, ax = plt.subplots(figsize=(10.4, 5.9))
    _plot_exact_curves(
        ax,
        curves,
        'plant_COP_or_EER',
        colors,
    )
    ax.plot(
        envelope['plant_load_kW'],
        envelope['plant_COP_or_EER'],
        color='black',
        linestyle=':',
        linewidth=2.2,
        label='Minimum power',
        zorder=5,
    )
    _add_crossover_lines(ax, crossover)
    style_axis_centered(
        fig,
        ax,
        title=(
            f"{mode.capitalize()}: selected efficiency envelope ({title_suffix})"
        ),
        xlabel='Required plant load [kW]',
        ylabel=_eff_label(mode),
    )
    ax.legend(
        loc='upper left',
        bbox_to_anchor=(1.01, 1.0),
        borderaxespad=0.0,
    )
    save(
        fig,
        f"05_{mode}_selected_efficiency_envelope_1_vs_2_vs_3_"
        f"{_boundary_file_suffix(boundary)}.png",
        right=0.82,
    )

    # 06: Extra power figure with selected best envelope and crossover loads.
    fig, ax = plt.subplots(figsize=(10.4, 5.9))
    _plot_exact_curves(
        ax,
        curves,
        'plant_power_kW',
        colors,
    )
    ax.plot(
        envelope['plant_load_kW'],
        envelope['plant_power_kW'],
        color='black',
        linestyle=':',
        linewidth=2.2,
        label='Minimum power',
        zorder=5,
    )
    _add_crossover_lines(ax, crossover)
    style_axis_centered(
        fig,
        ax,
        title=(
            f"{mode.capitalize()}: selected power envelope ({title_suffix})"
        ),
        xlabel='Required plant load [kW]',
        ylabel=_unit_power_label(boundary),
    )
    ax.legend(
        loc='upper left',
        bbox_to_anchor=(1.01, 1.0),
        borderaxespad=0.0,
    )
    save(
        fig,
        f"06_{mode}_selected_power_envelope_1_vs_2_vs_3_"
        f"{_boundary_file_suffix(boundary)}.png",
        right=0.82,
    )


def main():
    for mode in ('heating', 'cooling'):
        plot_circuit_comparison(mode)
        plot_strategy(mode)
        plot_plant_dispatch(mode)
        plot_active_unit_comparison_curves(mode, BOUNDARY_TO_PLOT)
        if PLOT_ADDITIONAL_BOUNDARIES:
            other = 'with_unit_pump_screening' if BOUNDARY_TO_PLOT == 'chiller_only' else 'chiller_only'
            plot_active_unit_comparison_curves(mode, other)
    pass

if __name__ == '__main__':
    main()
