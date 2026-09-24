"""
16_plot_optimization_summary.py

Optimization summary plot:
- best tested local fixed-load efficiency improvements.

The plot is derived entirely from the parametric optimization result tables.
No comparison result tables are used.
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
PARAMETRIC_FOLDER = PROJECT_ROOT / '06_RESULTS' / 'optimization' / 'parametric'
OUTPUT_FOLDER = PROJECT_ROOT / '08_THESIS_EXPORT' / 'figures' / 'optimization'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

config = load_module('config_plot_optimization_summary', CONFIG_FILE)
table_io = load_module('table_io_plot_optimization_summary', TABLE_IO_FILE)
style = load_module('style_plot_optimization_summary', PLOT_STYLE_FILE)
style.setup_plot_theme()


def read_optional(path):
    return table_io.read_table(path) if table_io.table_exists(path) else pd.DataFrame()


def feasible_rows(data):
    if data.empty:
        return data
    q = data.copy()
    if 'model_status' in q.columns:
        q = q[q['model_status'].astype(str).eq('OK')]
    if 'feasible' in q.columns:
        q = q[q['feasible'].astype(str).str.lower().isin(['true', '1'])]
    return q


def add_gain(rows, study, mode, data, x_column, reference_x, metric):
    if data.empty:
        return
    q = data.copy()
    if 'mode' in q.columns:
        q = q[q['mode'].astype(str).str.lower().eq(mode)]
    q = feasible_rows(q)
    x = pd.to_numeric(q.get(x_column), errors='coerce')
    y = pd.to_numeric(q.get(metric), errors='coerce')
    valid = x.notna() & y.notna()
    q = q.loc[valid].copy()
    if q.empty:
        return
    x = pd.to_numeric(q[x_column], errors='coerce')
    y = pd.to_numeric(q[metric], errors='coerce')
    baseline_index = (x - float(reference_x)).abs().idxmin()
    best_index = y.idxmax()
    baseline = float(y.loc[baseline_index])
    best = float(y.loc[best_index])
    if baseline <= 0:
        return
    rows.append({'study': study, 'mode': mode, 'improvement_percent': 100.0 * (best / baseline - 1.0)})


def build_local_gains():
    rows = []
    add_gain(rows, 'Heating-water temperature', 'heating', read_optional(PARAMETRIC_FOLDER / '01_heating_water_temperature_fixed_load.csv'), 'water_out_C', config.HEATING_WATER_OUT_C, 'COP_or_EER_circuit')
    add_gain(rows, 'Cooling-water temperature', 'cooling', read_optional(PARAMETRIC_FOLDER / '02_cooling_water_temperature_fixed_load.csv'), 'water_out_C', config.COOLING_WATER_OUT_C, 'COP_or_EER_circuit')

    air = read_optional(PARAMETRIC_FOLDER / '05_air_UA_fixed_load.csv')
    water = read_optional(PARAMETRIC_FOLDER / '06_water_UA_fixed_load.csv')
    fan = read_optional(PARAMETRIC_FOLDER / '08_fan_speed_fixed_load.csv')
    flow = read_optional(PARAMETRIC_FOLDER / '09_water_flow_and_pump_fixed_load.csv')
    reference = read_optional(PARAMETRIC_FOLDER / '00_parametric_reference_points.csv')

    for mode in ('heating', 'cooling'):
        add_gain(rows, 'Air-side effective UA', mode, air, 'air_UA_multiplier', 1.0, 'COP_or_EER_circuit')
        add_gain(rows, 'Water-side effective UA', mode, water, 'water_UA_multiplier', 1.0, 'COP_or_EER_circuit')

        ref_fan = 1.0
        if not reference.empty:
            q = reference[reference['mode'].astype(str).str.lower().eq(mode)]
            if not q.empty:
                candidate = pd.to_numeric(pd.Series([q.iloc[0].get('reference_fan_speed_fraction')]), errors='coerce').iloc[0]
                if np.isfinite(candidate):
                    ref_fan = float(candidate)
        add_gain(rows, 'Fan speed', mode, fan, 'fan_speed_fraction', ref_fan, 'COP_or_EER_circuit')
        add_gain(rows, 'Water flow / unit-pump screening', mode, flow, 'water_flow_fraction', 1.0, 'COP_or_EER_with_unit_pump_screening')

    return pd.DataFrame(rows)


def main():
    gains = build_local_gains()
    if not gains.empty:
        gains['label'] = gains['study'].astype(str) + ' | ' + gains['mode'].astype(str).str.capitalize()
        gains = gains.sort_values('improvement_percent')
        fig, ax = plt.subplots(figsize=(10.6, 6.2))
        ax.barh(
            gains['label'], gains['improvement_percent'],
            color=[style.MODE_COLOR.get(str(mode).lower(), style.TEAL) for mode in gains['mode']],
        )
        style.style_axis(ax, xlabel='COP / EER improvement vs reference [%]', grid_axis='x')
        style.save_figure(fig, OUTPUT_FOLDER / '01_local_fixed_load_efficiency_gains.png', dpi=config.PLOT_DPI, bottom=0.10)

    pass


if __name__ == '__main__':
    main()
