"""
08_plot_actual_circuit_staging.py

Plots the retained observed stable circuit-configuration counts only.
"""

from pathlib import Path
import importlib.util
import sys

import pandas as pd
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = PROJECT_ROOT / '00_CONFIG' / 'config.py'
TABLE_IO_FILE = PROJECT_ROOT / '00_CONFIG' / 'table_io.py'
PLOT_STYLE_FILE = PROJECT_ROOT / '00_CONFIG' / 'plot_style.py'
INPUT_CONFIGURATION_SUMMARY = PROJECT_ROOT / '06_RESULTS' / 'validation' / 'staging_configuration_summary.csv'
OUTPUT_FOLDER = PROJECT_ROOT / '08_THESIS_EXPORT' / 'figures' / 'validation'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

config = load_module('config_plot_staging', CONFIG_FILE)
table_io = load_module('table_io_plot_staging', TABLE_IO_FILE)
style = load_module('style_plot_staging', PLOT_STYLE_FILE)
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


def main():
    if not table_io.table_exists(INPUT_CONFIGURATION_SUMMARY):
        return
    configuration = table_io.read_table(INPUT_CONFIGURATION_SUMMARY)
    if configuration.empty:
        return

    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    pivot = configuration.pivot_table(
        index='unit', columns='active_configuration', values='stable_periods',
        aggfunc='sum', fill_value=0,
    )
    pivot.plot(kind='bar', ax=ax)
    add_bar_labels(ax, fmt='{:.0f}', fontsize=style.BAR_VALUE_FONTSIZE, rotation=90)
    style.style_axis(
        ax,
        title='Observed stable circuit configurations',
        xlabel='Physical Chiller Unit',
        ylabel='Stable periods [-]',
        grid_axis='y',
    )
    ax.legend(title='Configuration', loc='upper left', bbox_to_anchor=(1.01, 1.0), borderaxespad=0.0)
    style.save_figure(
        fig, OUTPUT_FOLDER / '07_observed_circuit_configurations.png',
        dpi=config.PLOT_DPI, right=0.82,
    )
    pass


if __name__ == '__main__':
    main()
