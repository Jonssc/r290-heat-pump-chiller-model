"""
13_plot_annual_plant.py

Measured + reconstructed annual plant plots. Reconstruction and plant dispatch are not recalculated here.
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
INPUT_5MIN = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_5min_plant_results.csv'
INPUT_MONTHLY = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_monthly_plant_summary.csv'
INPUT_HERA_HOURS = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_active_HERA_hours.csv'
INPUT_CIRCUIT_HOURS = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_active_circuit_hours.csv'
OUTPUT_FOLDER = PROJECT_ROOT / '08_THESIS_EXPORT' / 'figures' / 'annual' / 'plant'


# ============================================================
# 3. PLOT SELECTION
# ============================================================

PLOT_ANNUAL_TIMELINE = True
PLOT_MONTHLY_ENERGY = True
PLOT_ACTIVE_HERA_HOURS = True
PLOT_ACTIVE_CIRCUIT_HOURS = True
PLOT_FREQUENCY_DISTRIBUTION = False



# ============================================================
# 4. MODULE LOADING
# ============================================================

def load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    sys.modules[n] = m
    s.loader.exec_module(m)
    return m
c = load('cfg_pap', CONFIG_FILE)
tab = load('tab_pap', TABLE_IO_FILE)
style = load('sty_pap', PLOT_STYLE_FILE)
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



# ============================================================
# 6. MAIN
# ============================================================

def main():
    p = read(INPUT_5MIN)
    m = read(INPUT_MONTHLY)
    h = read(INPUT_HERA_HOURS)
    ci = read(INPUT_CIRCUIT_HOURS)
    if PLOT_ANNUAL_TIMELINE and (not p.empty):
        p['timestamp'] = pd.to_datetime(p.timestamp, errors='coerce')
        daily = p.set_index('timestamp').resample('1D').agg(heating_kW=('Heating_load_final_kW', 'mean'), cooling_kW=('Cooling_load_final_kW', 'mean')).reset_index()
        fig, ax = plt.subplots(figsize=(12, 5.6))
        ax.plot(daily.timestamp, daily.heating_kW, lw=1.8, color=style.HEATING_COLOR, label='Heating')
        ax.plot(daily.timestamp, daily.cooling_kW, lw=1.8, color=style.COOLING_COLOR, label='Cooling')
        style.style_axis(ax, title='355-day measured + reconstructed building load', xlabel='Date', ylabel='Thermal demand [kW]')
        ax.legend()
        fig.autofmt_xdate(rotation=25)
        save(fig, '01_annual_load_timeline.png')
    if PLOT_MONTHLY_ENERGY and (not m.empty):
        x = np.arange(len(m))
        w = 0.25
        fig, ax = plt.subplots(figsize=(10.5, 5.8))
        b1 = ax.bar(x - w, m.heating_MWh, w, color=style.HEATING_COLOR, label='Heating thermal')
        b2 = ax.bar(x, m.cooling_MWh, w, color=style.COOLING_COLOR, label='Cooling thermal')
        b3 = ax.bar(x + w, m.HERA_electricity_MWh, w, color=style.TEAL, label='Chiller Unit electricity')
        add_bar_labels(ax, [b1, b2, b3], fmt='{:.1f}', fontsize=style.BAR_VALUE_FONTSIZE, rotation=90, skip_zero=True)
        style.style_axis(ax, title='Monthly building demand and modeled Chiller Unit electricity', xlabel='Month', ylabel='Energy [MWh]', grid_axis='y')
        ax.set_xticks(x)
        ax.set_xticklabels(m.month, rotation=35, ha='right')
        ax.legend()
        ymax = float(np.nanmax([m.heating_MWh.max(), m.cooling_MWh.max(), m.HERA_electricity_MWh.max()]))
        ax.set_ylim(0, ymax * 1.15)
        save(fig, '02_monthly_plant_energy.png')
    if PLOT_ACTIVE_HERA_HOURS and (not h.empty):
        fig, ax = plt.subplots(figsize=(8.8, 5.3))
        bars = ax.bar(h.active_HERA_units.astype(str), h.hours, color=style.TEAL)
        add_bar_labels(ax, [bars], fmt='{:.0f}')
        style.style_axis(ax, title='Modeled active Chiller Unit duration', xlabel='Active Chiller Units [-]', ylabel='Hours [h]', grid_axis='y')
        ax.set_ylim(0, float(h.hours.max()) * 1.12)
        save(fig, '03_active_chiller_unit_hours.png')
    if PLOT_ACTIVE_CIRCUIT_HOURS and (not ci.empty):
        fig, ax = plt.subplots(figsize=(8.8, 5.3))
        bars = ax.bar(ci.active_circuits.astype(str), ci.hours, color=style.YELLOW)
        add_bar_labels(ax, [bars], fmt='{:.0f}')
        style.style_axis(ax, title='Modeled active-circuit duration', xlabel='Active refrigerant circuits [-]', ylabel='Hours [h]', grid_axis='y')
        ax.set_ylim(0, float(ci.hours.max()) * 1.12)
        save(fig, '04_active_circuit_hours.png')
if __name__ == '__main__':
    main()
