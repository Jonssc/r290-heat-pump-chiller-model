"""
14_plot_heat_recovery.py

Retained dedicated water/water heat-recovery figures at the single reference
UA case. The discarded UA-sensitivity figure and supporting sensitivity table
have been removed.
"""

from pathlib import Path
import importlib.util
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = PROJECT_ROOT / '00_CONFIG' / 'config.py'
TABLE_IO_FILE = PROJECT_ROOT / '00_CONFIG' / 'table_io.py'
PLOT_STYLE_FILE = PROJECT_ROOT / '00_CONFIG' / 'plot_style.py'
INPUT_SUMMARY = PROJECT_ROOT / '06_RESULTS' / 'optimization' / 'heat_recovery' / 'hybrid_water_water_summary.csv'
OUTPUT_FOLDER = PROJECT_ROOT / '08_THESIS_EXPORT' / 'figures' / 'optimization' / 'heat_recovery'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

config = load('config_plot_heat_recovery', CONFIG_FILE)
table_io = load('table_io_plot_heat_recovery', TABLE_IO_FILE)
style = load('style_plot_heat_recovery', PLOT_STYLE_FILE)
style.setup_plot_theme()




def add_bar_labels(ax, containers=None, fmt=None, fontsize=style.BAR_VALUE_FONTSIZE, rotation=0):
    if containers is None:
        containers = ax.containers
    for container in containers:
        labels = []
        for bar in container:
            h = bar.get_height()
            if fmt is None:
                if abs(h - round(h)) < 1e-6:
                    label = f"{int(round(h))}"
                elif abs(h) >= 10:
                    label = f"{h:.1f}"
                else:
                    label = f"{h:.2f}"
            elif callable(fmt):
                label = fmt(h)
            else:
                label = fmt.format(h)
            labels.append(label)
        ax.bar_label(container, labels=labels, padding=3, fontsize=fontsize, rotation=rotation)


def metric(summary, name, unit=None):
    q = summary[summary['metric'].astype(str).eq(name)]
    if unit is not None:
        q = q[q['unit'].astype(str).eq(unit)]
    if q.empty:
        return np.nan
    return float(pd.to_numeric(q.iloc[0]['value'], errors='coerce'))


def main():
    if not table_io.table_exists(INPUT_SUMMARY):
        return
    summary = table_io.read_table(INPUT_SUMMARY)

    reference = metric(summary, 'Existing air/water reference electricity', 'MWh_el')
    recovery = metric(summary, 'Dedicated water/water heat-recovery electricity', 'MWh_el')
    recovered_cooling = metric(summary, 'Recovered cooling thermal energy', 'MWh_th')
    recovered_heating = metric(summary, 'Recovered heating thermal energy', 'MWh_th')

    if np.isfinite(reference) and np.isfinite(recovery):
        # Keep the comparison fully data-driven. The saving is calculated
        # directly from the two bar values so it automatically updates after
        # the heat-recovery analysis is rerun with new hybrid-period data.
        saving_mwh = reference - recovery
        saving_percent = (
            100.0 * saving_mwh / reference
            if reference > 0
            else np.nan
        )

        fig, ax = plt.subplots(figsize=(8.4, 5.6))
        labels = ['Without heat\nrecovery', 'With heat\nrecovery']
        values = [reference, recovery]
        bars, _ = style.fixed_width_bars(
            ax,
            labels,
            values,
            color=[style.POINT_GREY, style.TEAL],
            width=0.55,
        )
        for bar, value in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value,
                f'{value:.2f}',
                ha='center',
                va='bottom',
                fontsize=style.BAR_VALUE_FONTSIZE,
            )

        ymax = max(values)
        if np.isfinite(ymax) and ymax > 0:
            ax.set_ylim(0.0, 1.22 * ymax)

        if np.isfinite(saving_mwh) and np.isfinite(saving_percent):
            ax.text(
                0.5,
                0.94,
                f'Electricity saving: {saving_mwh:.2f} MWh ({saving_percent:.1f}%)',
                transform=ax.transAxes,
                ha='center',
                va='top',
                fontsize=16,
            )

        style.style_axis(
            ax,
            title='Hybrid-period electrical energy',
            ylabel='Electricity [MWh]',
            grid_axis='y',
        )
        style.save_figure(
            fig,
            OUTPUT_FOLDER / '01_reference_vs_heat_recovery_electricity.png',
            dpi=config.PLOT_DPI,
        )

    if np.isfinite(recovered_cooling) and np.isfinite(recovered_heating):
        fig, ax = plt.subplots(figsize=(7.9, 5.4))
        bars, _ = style.fixed_width_bars(
            ax,
            ['Recovered\ncooling', 'Recovered\nheating'],
            [recovered_cooling, recovered_heating],
            color=[style.COOLING_COLOR, style.HEATING_COLOR],
            width=0.55,
        )
        add_bar_labels(ax, [bars], fmt='{:.2f}')
        ymax = max(recovered_cooling, recovered_heating)
        if np.isfinite(ymax) and ymax > 0:
            ax.set_ylim(0.0, 1.12 * ymax)
        style.style_axis(
            ax,
            title='Recovered thermal energy during modeled hybrid periods',
            ylabel='Thermal energy [MWh]',
            grid_axis='y',
        )
        style.save_figure(fig, OUTPUT_FOLDER / '02_recovered_heating_cooling_energy.png', dpi=config.PLOT_DPI)

    pass


if __name__ == '__main__':
    main()
