"""
12_plot_hybrid_operation.py

Retained measured hybrid-operation figures. The operating-state-hours bar chart
has been removed from the final thesis code.
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
INPUT_POINTS = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'hybrid_classified_points.csv'
INPUT_MONTHLY = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'hybrid_monthly_summary.csv'
OUTPUT_FOLDER = PROJECT_ROOT / '08_THESIS_EXPORT' / 'figures' / 'annual' / 'hybrid'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

config = load('config_plot_hybrid', CONFIG_FILE)
table_io = load('table_io_plot_hybrid', TABLE_IO_FILE)
style = load('style_plot_hybrid', PLOT_STYLE_FILE)
style.setup_plot_theme()


def read(path):
    return table_io.read_table(path) if table_io.table_exists(path) else pd.DataFrame()


def save(fig, filename):
    style.save_figure(fig, OUTPUT_FOLDER / filename, dpi=config.PLOT_DPI)


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


def main():
    points = read(INPUT_POINTS)
    monthly = read(INPUT_MONTHLY)

    if not monthly.empty:
        fig, ax = plt.subplots(figsize=(9.8, 5.6))
        bars, _ = style.fixed_width_bars(
            ax, monthly['month'].astype(str), monthly['recoverable_overlap_MWh'],
            color=style.TEAL, width=0.55, rotation=35, ha='right',
        )
        add_bar_labels(ax, [bars], fmt='{:.1f}', fontsize=style.BAR_VALUE_FONTSIZE)
        max_overlap = pd.to_numeric(
            monthly['recoverable_overlap_MWh'],
            errors='coerce',
        ).max()
        if np.isfinite(max_overlap) and max_overlap > 0:
            ax.set_ylim(0.0, float(max_overlap) * 1.12)
        style.style_axis(
            ax,
            title='Monthly first-order heat-recovery opportunity',
            xlabel='Month',
            ylabel='Thermal overlap [MWh]',
            grid_axis='y',
        )
        save(fig, '01_monthly_recoverable_overlap.png')

    if not points.empty:
        hybrid = points[points['Operating_state'].astype(str).eq('Hybrid')]
        values = pd.to_numeric(hybrid['Recoverable_overlap_kW'], errors='coerce').dropna().sort_values(ascending=False).to_numpy()
        if len(values):
            x = 100.0 * np.arange(1, len(values) + 1) / len(values)
            fig, ax = plt.subplots(figsize=(9.5, 5.6))
            ax.plot(x, values, lw=2.4, color=style.TEAL)
            style.style_axis(
                ax,
                title='Recoverable thermal-power duration curve',
                xlabel='Hybrid-period exceedance [%]',
                ylabel='Recoverable thermal overlap [kW]',
            )
            save(fig, '02_recoverable_thermal_power_duration.png')

        if not hybrid.empty:
            fig, ax = plt.subplots(figsize=(7.6, 6.1))
            ax.scatter(
                hybrid['Heating_load_filtered_kW'], hybrid['Cooling_load_filtered_kW'],
                s=18, alpha=0.28, color=style.POINT_GREY, edgecolors='none',
            )
            style.style_axis(
                ax,
                title='Measured simultaneous heating and cooling',
                xlabel='Heating demand [kW]',
                ylabel='Cooling demand [kW]',
            )
            save(fig, '03_hybrid_heating_vs_cooling.png')

    pass


if __name__ == '__main__':
    main()
