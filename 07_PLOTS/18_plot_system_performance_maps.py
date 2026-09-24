"""
18_plot_system_performance_maps.py

Detailed component-optimization contour maps:
- air-side UA x fan-speed multiplier;
- water-side UA x flow fraction.

Discarded setpoint, staging/frequency, active-unit/circuit and hybrid maps have
been removed from the final code.
"""

from pathlib import Path
import importlib.util
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm
from scipy.interpolate import RegularGridInterpolator, RectBivariateSpline

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = PROJECT_ROOT / '00_CONFIG' / 'config.py'
TABLE_IO_FILE = PROJECT_ROOT / '00_CONFIG' / 'table_io.py'
PLOT_STYLE_FILE = PROJECT_ROOT / '00_CONFIG' / 'plot_style.py'
INPUT_FOLDER = PROJECT_ROOT / '06_RESULTS' / 'optimization' / 'parametric'
OUTPUT_FOLDER = PROJECT_ROOT / '08_THESIS_EXPORT' / 'figures' / 'optimization' / 'parametric'

INFEASIBLE_GREY = '#E5E7EB'
FIGSIZE = (9.8, 6.1)
INTERPOLATION_FACTOR = 6


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

config = load_module('config_plot_component_maps', CONFIG_FILE)
table_io = load_module('table_io_plot_component_maps', TABLE_IO_FILE)
style = load_module('style_plot_component_maps', PLOT_STYLE_FILE)
style.setup_plot_theme()


def read_table(stem):
    path = INPUT_FOLDER / f'{stem}.csv'
    return table_io.read_table(path) if table_io.table_exists(path) else pd.DataFrame()


def save(fig, filename):
    style.save_figure(fig, OUTPUT_FOLDER / filename, dpi=config.PLOT_DPI)


def prepare_pivot(data, x_column, y_column, value_column):
    q = data.copy()
    if 'model_status' in q.columns:
        q = q[q['model_status'].astype(str).eq('OK')]
    if 'feasible' in q.columns:
        q = q[q['feasible'].astype(str).str.lower().isin(['true', '1'])]
    for column in (x_column, y_column, value_column):
        q[column] = pd.to_numeric(q[column], errors='coerce')
    q = q.dropna(subset=[x_column, y_column, value_column])
    if q.empty:
        return None
    return q.pivot_table(index=y_column, columns=x_column, values=value_column, aggfunc='mean').sort_index().sort_index(axis=1)


def interpolate(pivot):
    x = pivot.columns.to_numpy(float)
    y = pivot.index.to_numpy(float)
    z = pivot.to_numpy(float)
    valid = np.isfinite(z)
    fill = pd.DataFrame(z).interpolate(axis=0, limit_direction='both').interpolate(axis=1, limit_direction='both').to_numpy()
    xi = np.linspace(x.min(), x.max(), max(len(x) * INTERPOLATION_FACTOR, len(x)))
    yi = np.linspace(y.min(), y.max(), max(len(y) * INTERPOLATION_FACTOR, len(y)))
    XX, YY = np.meshgrid(xi, yi)
    points = np.column_stack([YY.ravel(), XX.ravel()])
    if len(y) >= 4 and len(x) >= 4:
        spline = RectBivariateSpline(y, x, fill, kx=min(3, len(y)-1), ky=min(3, len(x)-1), s=0.0)
        zi = spline(yi, xi)
    else:
        zi = RegularGridInterpolator((y, x), fill, method='linear', bounds_error=False, fill_value=np.nan)(points).reshape(len(yi), len(xi))
    # Keep the interpolated rectangular field instead of reapplying a nearest
    # valid-data mask. The mask clipped tiny edge regions near the lower-left
    # corner after the user-requested axis limits, which appeared as white
    # wedges in plots 01, 03 and 06.
    return xi, yi, zi


def apply_ua_axis_limits(ax, x_column, y_column):
    if str(x_column) in {'air_UA_multiplier', 'water_UA_multiplier'}:
        ax.set_xlim(0.8, 1.6)
    if str(y_column) in {'air_UA_multiplier', 'water_UA_multiplier'}:
        ax.set_ylim(0.8, 1.6)




def colorbar_ticks_with_endpoints(levels_array, ticks_array=None):
    levels_array = np.asarray(levels_array, dtype=float)
    if ticks_array is None:
        ticks_array = np.array([], dtype=float)
    ticks_array = np.asarray(ticks_array, dtype=float)
    ticks_array = ticks_array[np.isfinite(ticks_array)]
    merged = np.unique(np.concatenate(([levels_array[0]], ticks_array, [levels_array[-1]])))
    return merged

def levels(values, step):
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return None
    start = np.floor(finite.min() / step) * step
    end = np.ceil(finite.max() / step) * step
    if np.isclose(start, end):
        end = start + step
    return np.arange(start, end + 0.5 * step, step)


def contour(data, *, x_column, y_column, value_column, title, xlabel, ylabel, cbar_label, filename, step, decimals):
    pivot = prepare_pivot(data, x_column, y_column, value_column)
    if pivot is None:
        return
    x, y, z = interpolate(pivot)
    lev = levels(z, step)
    if lev is None:
        return
    X, Y = np.meshgrid(x, y)
    masked = np.ma.masked_invalid(z)
    fig, ax = plt.subplots(figsize=FIGSIZE)
    ax.set_facecolor(INFEASIBLE_GREY)
    norm = BoundaryNorm(lev, ncolors=256, clip=True)
    filled = ax.contourf(X, Y, masked, levels=lev, norm=norm, extend='neither', corner_mask=False)
    lines = ax.contour(X, Y, masked, levels=lev, colors='black', linewidths=0.8, corner_mask=False)
    ax.clabel(lines, inline=True, fontsize=7.5, fmt=f'%.{decimals}f')
    cbar = fig.colorbar(filled, ax=ax, extend='neither')
    cbar.set_label(cbar_label)
    cbar.set_ticks(colorbar_ticks_with_endpoints(lev, cbar.get_ticks()))
    cbar.ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, pos: f'{v:.{decimals}f}'))
    style.style_axis(ax, title=title, xlabel=xlabel, ylabel=ylabel, grid_axis='none')
    apply_ua_axis_limits(ax, x_column, y_column)
    save(fig, filename)


def main():
    air_heating = read_table('14_heating_air_UA_fan_map')
    air_cooling = read_table('15_cooling_air_UA_fan_map')
    water_heating = read_table('16_heating_water_UA_flow_map')
    water_cooling = read_table('17_cooling_water_UA_flow_map')

    contour(air_heating, x_column='air_UA_multiplier', y_column='fan_speed_fraction', value_column='COP_or_EER_circuit', title='Heating: air-side UA and fan-speed efficiency', xlabel='Air-side effective UA multiplier [-]', ylabel='Fan-speed multiplier [-]', cbar_label='Circuit COP [-]', filename='14_heating_COP_vs_air_UA_vs_fan.png', step=0.2, decimals=1)
    contour(air_cooling, x_column='air_UA_multiplier', y_column='fan_speed_fraction', value_column='COP_or_EER_circuit', title='Cooling: air-side UA and fan-speed efficiency', xlabel='Air-side effective UA multiplier [-]', ylabel='Fan-speed multiplier [-]', cbar_label='Circuit EER [-]', filename='15_cooling_EER_vs_air_UA_vs_fan.png', step=0.2, decimals=1)
    contour(air_heating, x_column='air_UA_multiplier', y_column='fan_speed_fraction', value_column='electrical_saving_vs_reference_percent', title='Heating: electricity saving from air-side UA and fan speed', xlabel='Air-side effective UA multiplier [-]', ylabel='Fan-speed multiplier [-]', cbar_label='Electrical saving vs reference [%]', filename='16_heating_saving_vs_air_UA_vs_fan.png', step=2.0, decimals=0)
    contour(air_cooling, x_column='air_UA_multiplier', y_column='fan_speed_fraction', value_column='electrical_saving_vs_reference_percent', title='Cooling: electricity saving from air-side UA and fan speed', xlabel='Air-side effective UA multiplier [-]', ylabel='Fan-speed multiplier [-]', cbar_label='Electrical saving vs reference [%]', filename='17_cooling_saving_vs_air_UA_vs_fan.png', step=2.0, decimals=0)
    contour(water_heating, x_column='water_UA_multiplier', y_column='water_flow_fraction', value_column='electrical_saving_vs_reference_percent', title='Heating: electricity saving from water-side UA and flow', xlabel='Water-side effective UA multiplier [-]', ylabel='Water-flow / pump-speed fraction [-]', cbar_label='Electrical saving [%]', filename='18_heating_saving_vs_water_UA_vs_flow_with_pump.png', step=2.0, decimals=0)
    contour(water_cooling, x_column='water_UA_multiplier', y_column='water_flow_fraction', value_column='electrical_saving_vs_reference_percent', title='Cooling: electricity saving from water-side UA and flow', xlabel='Water-side effective UA multiplier [-]', ylabel='Water-flow / pump-speed fraction [-]', cbar_label='Electrical saving [%]', filename='19_cooling_saving_vs_water_UA_vs_flow_with_pump.png', step=2.0, decimals=0)

    pass


if __name__ == '__main__':
    main()
