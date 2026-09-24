"""
11_plot_annual_load.py

Measured annual building-load plots. The thermodynamic model is never recalculated here.
"""


# ============================================================
# 1. IMPORTS
# ============================================================

from pathlib import Path
import importlib.util, sys
import numpy as np, pandas as pd, matplotlib.pyplot as plt


# ============================================================
# 2. FILES USED BY THIS SCRIPT
#    CHANGE THESE PATHS HERE IF A DIFFERENT RESULT FILE IS USED
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = PROJECT_ROOT / '00_CONFIG' / 'config.py'
TABLE_IO_FILE = PROJECT_ROOT / '00_CONFIG' / 'table_io.py'
PLOT_STYLE_FILE = PROJECT_ROOT / '00_CONFIG' / 'plot_style.py'
INPUT_DIAGNOSTICS = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_load_diagnostics.csv'
INPUT_TRENDS = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_load_outdoor_trends.csv'
INPUT_MONTHLY = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_monthly_measured_thermal_energy.csv'
OUTPUT_FOLDER = PROJECT_ROOT / '08_THESIS_EXPORT' / 'figures' / 'annual' / 'loads'


# ============================================================
# 3. PLOT SELECTION
# ============================================================

PLOT_HEATING_LOAD_VS_OUTDOOR = True
PLOT_COOLING_LOAD_VS_OUTDOOR = True
PLOT_MONTHLY_MEASURED_ENERGY = True



# ============================================================
# 4. MODULE LOADING
# ============================================================

def load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    sys.modules[n] = m
    s.loader.exec_module(m)
    return m
c = load('cfg_pal', CONFIG_FILE)
tab = load('tab_pal', TABLE_IO_FILE)
style = load('sty_pal', PLOT_STYLE_FILE)
style.setup_plot_theme()



# ============================================================
# 5. TABLE / PLOT HELPERS
# ============================================================

def read(p):
    return tab.read_table(p if p.exists() else p.with_suffix('.csv')) if p.exists() or p.with_suffix('.csv').exists() else pd.DataFrame()

def save(fig, n):
    style.save_figure(fig, OUTPUT_FOLDER / n, dpi=c.PLOT_DPI)


def add_bar_labels(ax, containers=None, fmt=None, fontsize=style.BAR_VALUE_FONTSIZE, rotation=0, skip_zero=False):
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
            if skip_zero and np.isclose(h, 0.0):
                label = ''
            labels.append(label)
        ax.bar_label(container, labels=labels, padding=3, fontsize=fontsize, rotation=rotation)

def scatter(diag, trends, col, series, color, title, ylabel, name):
    q = diag[['Outdoor_C', col]].dropna()
    t = trends[trends.series.astype(str).eq(series)] if not trends.empty else pd.DataFrame()
    fig, ax = plt.subplots(figsize=(9.8, 5.8))
    ax.scatter(q.Outdoor_C, q[col], s=13, alpha=0.22, color=style.POINT_GREY, edgecolors='none', label='5-min measured data')
    if not t.empty:
        ax.plot(t.outdoor_bin_C, t.trend_kW, lw=3, color=color, label='Smoothed 1 °C-bin trend')
    style.style_axis(ax, title=title, xlabel='Outdoor temperature [°C]', ylabel=ylabel)
    ax.legend(loc='best')
    save(fig, name)



# ============================================================
# 6. MAIN
# ============================================================

def main():
    d = read(INPUT_DIAGNOSTICS)
    t = read(INPUT_TRENDS)
    m = read(INPUT_MONTHLY)
    if PLOT_HEATING_LOAD_VS_OUTDOOR and (not d.empty):
        scatter(d, t, 'Heating_load_filtered_kW', 'Total_heating', style.HEATING_COLOR, 'Measured heating demand vs outdoor temperature', 'Heating demand [kW]', '01_heating_load_vs_outdoor.png')
    if PLOT_COOLING_LOAD_VS_OUTDOOR and (not d.empty):
        scatter(d, t, 'Cooling_load_filtered_kW', 'Total_cooling', style.COOLING_COLOR, 'Measured cooling demand vs outdoor temperature', 'Cooling demand [kW]', '02_cooling_load_vs_outdoor.png')
    if PLOT_MONTHLY_MEASURED_ENERGY and (not m.empty):
        x = np.arange(len(m))
        w = 0.38
        fig, ax = plt.subplots(figsize=(10.2, 5.8))
        b1 = ax.bar(x - w / 2, m.heating_MWh, w, color=style.HEATING_COLOR, label='Heating')
        b2 = ax.bar(x + w / 2, m.cooling_MWh, w, color=style.COOLING_COLOR, label='Cooling')
        add_bar_labels(ax, [b1, b2], fmt='{:.1f}', fontsize=style.BAR_VALUE_FONTSIZE, rotation=90, skip_zero=True)
        max_energy = np.nanmax(
            np.concatenate([
                pd.to_numeric(m.heating_MWh, errors='coerce').to_numpy(float),
                pd.to_numeric(m.cooling_MWh, errors='coerce').to_numpy(float),
            ])
        )
        if np.isfinite(max_energy) and max_energy > 0:
            ax.set_ylim(0.0, max_energy * 1.12)
        style.style_axis(ax, title='Measured monthly thermal energy', xlabel='Month', ylabel='Thermal energy [MWh]', grid_axis='y')
        ax.set_xticks(x)
        ax.set_xticklabels(m.month, rotation=35, ha='right')
        ax.legend()
        save(fig, '03_monthly_measured_thermal_energy.png')
if __name__ == '__main__':
    main()
