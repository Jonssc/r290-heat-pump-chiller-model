"""
13_annual_load_analysis.py

Measured building-load analysis using the corrected hydraulic interpretation.

OE404 is the heating branch. OE405 is the reversible ventilation branch.
The OE405 setpoint classifies ventilation heating/cooling before total loads are
formed. Missing OE405 values remain missing and are never silently replaced by
zero. Isolated spikes are filtered with the configured Hampel/MAD method.

No annual reconstruction and no plots are performed in this script.
"""


# ============================================================
# 1. IMPORTS
# ============================================================

from pathlib import Path
import importlib.util, sys
import numpy as np, pandas as pd


# ============================================================
# 2. FILES USED BY THIS SCRIPT
#    CHANGE THESE PATHS HERE IF A DIFFERENT FILE IS USED
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = PROJECT_ROOT / '00_CONFIG' / 'config.py'
TABLE_IO_FILE = PROJECT_ROOT / '00_CONFIG' / 'table_io.py'
RECONSTRUCTION_MODEL_FILE = PROJECT_ROOT / '03_MODELS' / 'annual_reconstruction_model.py'
INPUT_ANNUAL_LOAD_DATA = PROJECT_ROOT / '02_PROCESSED_DATA' / 'kiona_annual_clean.csv'
OUTPUT_DIAGNOSTICS = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_load_diagnostics'
OUTPUT_TRENDS = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_load_outdoor_trends'
OUTPUT_MONTHLY = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_monthly_measured_thermal_energy'
OUTPUT_SUMMARY = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_measured_load_summary'



# ============================================================
# 3. MODULE LOADING
# ============================================================

def load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    sys.modules[n] = m
    s.loader.exec_module(m)
    return m
c = load('cfg_annload', CONFIG_FILE)
tab = load('tab_annload', TABLE_IO_FILE)
m = load('recon_annload', RECONSTRUCTION_MODEL_FILE)



# ============================================================
# 4. MEASURED LOAD ANALYSIS
# ============================================================

def main():
    if not INPUT_ANNUAL_LOAD_DATA.exists():
        raise FileNotFoundError('Run 12_clean_kiona_annual.py first.')
    d = tab.read_table(INPUT_ANNUAL_LOAD_DATA)
    d['timestamp'] = pd.to_datetime(d.timestamp, errors='coerce')
    d = d[(d.timestamp >= pd.Timestamp(c.ANNUAL_START_DATE)) & (d.timestamp < pd.Timestamp(c.ANNUAL_END_DATE_EXCLUSIVE))].copy()
    for col in ['OE404_thermal_power_kW', 'OE405_thermal_power_kW']:
        d[col] = pd.to_numeric(d[col], errors='coerce')
        d.loc[d[col] < 0, col] = np.nan
    d['Ventilation_mode'] = m.classify_ventilation_mode(d.Ventilation_setpoint_C, c.ANNUAL_VENT_HEATING_SETPOINT_MIN_C, c.ANNUAL_VENT_COOLING_SETPOINT_MAX_C)
    d['OE404_heating_raw_kW'] = d.OE404_thermal_power_kW
    d['OE405_branch_raw_kW'] = d.OE405_thermal_power_kW
    d['OE404_heating_filtered_kW'], hs = m.hampel_filter(d.OE404_heating_raw_kW, c.ANNUAL_HAMPEL_WINDOW_SAMPLES, c.ANNUAL_HAMPEL_MAD_FACTOR, c.ANNUAL_HAMPEL_MIN_ABS_SPIKE_KW)
    d['OE405_branch_filtered_kW'], vs = m.hampel_filter(d.OE405_branch_raw_kW, c.ANNUAL_HAMPEL_WINDOW_SAMPLES, c.ANNUAL_HAMPEL_MAD_FACTOR, c.ANNUAL_HAMPEL_MIN_ABS_SPIKE_KW)
    d['OE405_heating_component_filtered_kW'], d['OE405_cooling_component_filtered_kW'] = m.allocate_ventilation_power(d.OE405_branch_filtered_kW, d.Ventilation_mode)
    d['Heating_load_filtered_kW'] = d.OE404_heating_filtered_kW + d.OE405_heating_component_filtered_kW
    d['Cooling_load_filtered_kW'] = d.OE405_cooling_component_filtered_kW
    d['Heating_removed_as_spike'] = hs.astype(int)
    d['Cooling_removed_as_spike'] = vs.astype(int)
    trends = []
    for name, col in {'OE404_heating': 'OE404_heating_filtered_kW', 'OE405_ventilation_heating': 'OE405_heating_component_filtered_kW', 'OE405_ventilation_cooling': 'OE405_cooling_component_filtered_kW', 'Total_heating': 'Heating_load_filtered_kW', 'Total_cooling': 'Cooling_load_filtered_kW'}.items():
        t = m.fit_outdoor_trend(d, 'Outdoor_C', col, c.ANNUAL_OUTDOOR_BIN_C, c.ANNUAL_MIN_TREND_BIN_SAMPLES, c.ANNUAL_TREND_ROLLING_BINS)
        if not t.empty:
            t['series'] = name
            trends.append(t)
    trends = pd.concat(trends, ignore_index=True) if trends else pd.DataFrame()
    start = pd.Timestamp(year=c.ANNUAL_MONTHLY_START_YEAR, month=c.ANNUAL_MONTHLY_START_MONTH, day=1)
    end = pd.Timestamp(year=c.ANNUAL_MONTHLY_END_YEAR, month=c.ANNUAL_MONTHLY_END_MONTH, day=1) + pd.offsets.MonthBegin(1)
    q = d[(d.timestamp >= start) & (d.timestamp < end)].copy()
    q['month'] = q.timestamp.dt.to_period('M').astype(str)
    dt = c.SOURCE_TIMESTEP_MINUTES / 60
    monthly = q.groupby('month').agg(heating_MWh=('Heating_load_filtered_kW', lambda s: pd.to_numeric(s, errors='coerce').sum(min_count=1) * dt / 1000), cooling_MWh=('Cooling_load_filtered_kW', lambda s: pd.to_numeric(s, errors='coerce').sum(min_count=1) * dt / 1000), heating_valid_samples=('Heating_load_filtered_kW', 'count'), cooling_valid_samples=('Cooling_load_filtered_kW', 'count')).reset_index()
    summary = pd.DataFrame([{'metric': 'Maximum measured filtered heating load', 'value': d.Heating_load_filtered_kW.max(), 'unit': 'kW'}, {'metric': 'Median measured filtered heating load', 'value': d.Heating_load_filtered_kW.median(), 'unit': 'kW'}, {'metric': 'Maximum measured filtered cooling load', 'value': d.Cooling_load_filtered_kW.max(), 'unit': 'kW'}, {'metric': 'Median measured filtered cooling load', 'value': d.Cooling_load_filtered_kW.median(), 'unit': 'kW'}, {'metric': 'Heating spikes removed', 'value': int(hs.sum()), 'unit': 'samples'}, {'metric': 'Ventilation branch spikes removed', 'value': int(vs.sum()), 'unit': 'samples'}])
    tab.write_table(d, OUTPUT_DIAGNOSTICS, export_csv=True, export_xlsx=False, csv_separator=c.CSV_SEPARATOR, csv_decimal=c.CSV_DECIMAL, float_format=c.CSV_FLOAT_FORMAT, sheet_name='Diagnostics')
    tab.write_table(trends, OUTPUT_TRENDS, export_csv=c.EXPORT_CSV, export_xlsx=c.EXPORT_XLSX, csv_separator=c.CSV_SEPARATOR, csv_decimal=c.CSV_DECIMAL, float_format=c.CSV_FLOAT_FORMAT, sheet_name='Trends')
    tab.write_table(monthly, OUTPUT_MONTHLY, export_csv=c.EXPORT_CSV, export_xlsx=c.EXPORT_XLSX, csv_separator=c.CSV_SEPARATOR, csv_decimal=c.CSV_DECIMAL, float_format=c.CSV_FLOAT_FORMAT, sheet_name='Monthly')
    tab.write_table(summary, OUTPUT_SUMMARY, export_csv=c.EXPORT_CSV, export_xlsx=c.EXPORT_XLSX, csv_separator=c.CSV_SEPARATOR, csv_decimal=c.CSV_DECIMAL, float_format=c.CSV_FLOAT_FORMAT, sheet_name='Summary')
if __name__ == '__main__':
    main()
