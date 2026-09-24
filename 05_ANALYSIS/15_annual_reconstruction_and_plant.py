"""
15_annual_reconstruction_and_plant.py

Validated 355-day measured + reconstructed building-load and 3-HERA plant view.

Study period: 2025-08-11 to 2026-08-01 exclusive. Measured branch power is
retained wherever available. Missing periods are reconstructed from outdoor-
temperature component trends plus weekday/weekend and hour-of-day factors.

The plant calculation uses the V2 HERA model, three physical units, two circuits
per unit, the physical three-unit simultaneous heating/cooling constraint,
50 °C heating and 7 °C cooling targets, normal outdoor-coil fan power, and no
external water-pump power. Model-domain failures remain explicit.

No plots are created here.
"""


# ============================================================
# 1. IMPORTS
# ============================================================

from pathlib import Path
from functools import lru_cache
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
ANNUAL_PLANT_MODEL_FILE = PROJECT_ROOT / '03_MODELS' / 'annual_plant_model.py'
FRASCOLD_GRID_MODEL_FILE = PROJECT_ROOT / '03_MODELS' / 'frascold_grid_model.py'
HERA_MODEL_FILE = PROJECT_ROOT / '03_MODELS' / 'hera_model.py'
MODEL_FACTORY_FILE = PROJECT_ROOT / '03_MODELS' / 'model_factory.py'
PLANT_MODEL_FILE = PROJECT_ROOT / '03_MODELS' / 'plant_model.py'
INPUT_ANNUAL_DIAGNOSTICS = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_load_diagnostics.csv'
INPUT_FRASCOLD_DATABASE = PROJECT_ROOT / '06_RESULTS' / 'databases' / 'frascold_performance_grid.csv'
INPUT_HX_CALIBRATION = PROJECT_ROOT / '06_RESULTS' / 'databases' / 'hera_hx_calibration.csv'
INPUT_STANDARDIZED_SUMMARY = PROJECT_ROOT / '06_RESULTS' / 'carnot' / 'standardized_SCOP_SEER_summary.csv'
OUTPUT_RECONSTRUCTION_TRENDS = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_reconstruction_component_trends'
OUTPUT_SCHEDULE_FACTORS = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_reconstruction_schedule_factors'
OUTPUT_CROSS_VALIDATION = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_reconstruction_cross_validation'
OUTPUT_5MIN = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_5min_plant_results'
OUTPUT_MONTHLY = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_monthly_plant_summary'
OUTPUT_ACTIVE_HERA_HOURS = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_active_HERA_hours'
OUTPUT_ACTIVE_CIRCUIT_HOURS = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_active_circuit_hours'
OUTPUT_SUMMARY = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_plant_summary'
OUTPUT_STANDARD_COMPARISON = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_standardized_vs_building_specific'



# ============================================================
# 3. MODULE LOADING
# ============================================================

def load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    sys.modules[n] = m
    s.loader.exec_module(m)
    return m
c = load('cfg_annplant', CONFIG_FILE)
tab = load('tab_annplant', TABLE_IO_FILE)
recon = load('recon_annplant', RECONSTRUCTION_MODEL_FILE)
ann = load('annmodel_v2', ANNUAL_PLANT_MODEL_FILE)
grid = load('grid_annplant', FRASCOLD_GRID_MODEL_FILE)
hera = load('hera_annplant', HERA_MODEL_FILE)
factory = load('factory_annplant', MODEL_FACTORY_FILE)
plant = load('plant_annplant', PLANT_MODEL_FILE)



# ============================================================
# 4. HERA MODEL CONSTRUCTION
# ============================================================

def build_model():
    return factory.build_circuit_model(frascold_database=INPUT_FRASCOLD_DATABASE, calibration_file=INPUT_HX_CALIBRATION, config=c, table_io=tab, frascold_grid_module=grid, hera_module=hera, air_ht_exponent_override=c.ANNUAL_AIR_HT_EXPONENT)



# ============================================================
# 5. SMALL HELPERS
# ============================================================

def roundstep(x, step):
    return round(float(x) / float(step)) * float(step) if np.isfinite(x) else np.nan



# ============================================================
# 6. ANNUAL RECONSTRUCTION AND PLANT SIMULATION
# ============================================================

def main():
    if not INPUT_ANNUAL_DIAGNOSTICS.exists():
        raise FileNotFoundError('Run 13_annual_load_analysis.py first.')
    d = tab.read_table(INPUT_ANNUAL_DIAGNOSTICS)
    d['timestamp'] = pd.to_datetime(d.timestamp, errors='coerce')
    d = d[(d.timestamp >= pd.Timestamp(c.ANNUAL_START_DATE)) & (d.timestamp < pd.Timestamp(c.ANNUAL_END_DATE_EXCLUSIVE))].copy()
    d['date'] = d.timestamp.dt.floor('D')
    d['hour'] = d.timestamp.dt.hour
    d['weekend'] = d.timestamp.dt.dayofweek.ge(5).astype(int)
    rawmap = {'OE404_heating': 'OE404_heating_raw_kW', 'ventilation_heating': 'OE405_heating_component_filtered_kW', 'ventilation_cooling': 'OE405_cooling_component_filtered_kW'}
    d['OE404_heating_clean_kW'], d['OE404_heating_spike_removed'] = recon.component_hampel_filter(d['OE404_heating_raw_kW'], c.ANNUAL_HAMPEL_WINDOW_SAMPLES, c.ANNUAL_HAMPEL_MAD_FACTOR, c.ANNUAL_HAMPEL_MIN_ABS_SPIKE_KW)
    d['ventilation_heating_clean_kW'] = pd.to_numeric(d['OE405_heating_component_filtered_kW'], errors='coerce')
    d['ventilation_cooling_clean_kW'] = pd.to_numeric(d['OE405_cooling_component_filtered_kW'], errors='coerce')
    defs = [('OE404_heating', 'OE404_heating_clean_kW', None), ('ventilation_heating', 'ventilation_heating_clean_kW', 'Heating'), ('ventilation_cooling', 'ventilation_cooling_clean_kW', 'Cooling')]
    trend_models = {}
    trend_tables = []
    for name, col, required in defs:
        bins, x, y = recon.fit_component_trend(d, col, required, c.ANNUAL_RECONSTRUCTION_MIN_COMPONENT_BIN_SAMPLES, c.ANNUAL_RECONSTRUCTION_TREND_ROLLING_BINS)
        bins['component'] = name
        trend_tables.append(bins)
        trend_models[name] = (x, y)
    trends = pd.concat(trend_tables, ignore_index=True)
    baseH, baseC = recon.build_base_total_predictions(d, trend_models)
    factors = recon.fit_total_schedule_factors(d, baseH, baseC)
    predH, predC = recon.apply_total_schedule_factors(d, baseH, baseC, factors)
    ordinal = d.date.map(pd.Timestamp.toordinal)
    cvH = np.full(len(d), np.nan)
    cvC = np.full(len(d), np.nan)
    for parity in [0, 1]:
        testmask = ordinal % 2 == parity
        train = d.loc[~testmask].copy()
        test = d.loc[testmask].copy()
        fold = {}
        for name, col, required in defs:
            _, x, y = recon.fit_component_trend(train, col, required, c.ANNUAL_RECONSTRUCTION_MIN_COMPONENT_BIN_SAMPLES, c.ANNUAL_RECONSTRUCTION_TREND_ROLLING_BINS)
            fold[name] = (x, y)
        trH, trC = recon.build_base_total_predictions(train, fold)
        fac = recon.fit_total_schedule_factors(train, trH, trC)
        teH, teC = recon.build_base_total_predictions(test, fold)
        pH, pC = recon.apply_total_schedule_factors(test, teH, teC, fac)
        cvH[testmask.to_numpy()] = pH
        cvC[testmask.to_numpy()] = pC
    cvrows = []
    for mode, actual, pred in [('Heating', d.Heating_load_filtered_kW, cvH), ('Cooling', d.Cooling_load_filtered_kW, cvC)]:
        r = recon.active_fit_metrics(actual, pred, 5.0)
        r['mode'] = mode
        cvrows.append(r)
    cross = pd.DataFrame(cvrows)
    schedule_rows = []
    for mode, fac in factors.items():
        for (weekend, hour), value in fac.items():
            schedule_rows.append({'mode': mode, 'day_type': 'Weekend' if weekend else 'Weekday', 'hour': hour, 'load_multiplier': value})
    schedules = pd.DataFrame(schedule_rows)
    measH = pd.to_numeric(d.Heating_load_filtered_kW, errors='coerce')
    measC = pd.to_numeric(d.Cooling_load_filtered_kW, errors='coerce')
    d['Heating_load_reconstructed_kW'] = predH
    d['Cooling_load_reconstructed_kW'] = predC
    d['Heating_load_final_kW'] = measH.where(measH.notna(), predH)
    d['Cooling_load_final_kW'] = measC.where(measC.notna(), predC)
    d['Heating_load_source'] = np.where(measH.notna(), 'measured', 'reconstructed')
    d['Cooling_load_source'] = np.where(measC.notna(), 'measured', 'reconstructed')
    model, cal = build_model()

    @lru_cache(maxsize=None)
    def dispatch(to, qh, qc):
        return ann.fleet_dispatch(model, (1.0, 1.0, 1.0), qh, qc, to, c.ANNUAL_PLANT_HEATING_WATER_OUT_C, c.ANNUAL_PLANT_COOLING_WATER_OUT_C, c.ANNUAL_PLANT_CYCLING_DEGRADATION_COEFFICIENT, c.FREQUENCY_STEP_HZ)
    d['Outdoor_model_bin_C'] = d.Outdoor_C.apply(lambda x: roundstep(x, c.ANNUAL_PLANT_OUTDOOR_BIN_C))
    d['Heating_model_bin_kW'] = d.Heating_load_final_kW.fillna(0).clip(lower=0).apply(lambda x: roundstep(x, c.ANNUAL_PLANT_LOAD_BIN_KW))
    d['Cooling_model_bin_kW'] = d.Cooling_load_final_kW.fillna(0).clip(lower=0).apply(lambda x: roundstep(x, c.ANNUAL_PLANT_LOAD_BIN_KW))
    records = []
    for r in d.itertuples():
        records.append({'model_status': 'MISSING_OUTDOOR_TEMPERATURE'} if not np.isfinite(r.Outdoor_model_bin_C) else dispatch(float(r.Outdoor_model_bin_C), float(r.Heating_model_bin_kW), float(r.Cooling_model_bin_kW)))
    disp = pd.DataFrame(records)
    for col in disp.columns:
        d[f'plant_{col}'] = disp[col].to_numpy()
    dt = c.SOURCE_TIMESTEP_MINUTES / 60
    valid = d.plant_model_status.eq('OK')
    d['Heating_energy_kWh'] = d.Heating_load_final_kW * dt
    d['Cooling_energy_kWh'] = d.Cooling_load_final_kW * dt
    d['Plant_electricity_kWh'] = np.where(valid, pd.to_numeric(d.plant_plant_power_kW, errors='coerce') * dt, np.nan)
    d['month'] = d.timestamp.dt.to_period('M').astype(str)
    monthly = d.groupby('month').agg(heating_MWh=('Heating_energy_kWh', lambda s: pd.to_numeric(s, errors='coerce').sum(min_count=1) / 1000), cooling_MWh=('Cooling_energy_kWh', lambda s: pd.to_numeric(s, errors='coerce').sum(min_count=1) / 1000), HERA_electricity_MWh=('Plant_electricity_kWh', lambda s: pd.to_numeric(s, errors='coerce').sum(min_count=1) / 1000), model_valid_hours=('plant_model_status', lambda s: s.astype(str).eq('OK').sum() * dt)).reset_index()
    hh = d.loc[valid, 'plant_active_units_total'].value_counts().sort_index().rename_axis('active_HERA_units').reset_index(name='sample_count')
    hh['hours'] = hh.sample_count * dt
    ch = d.loc[valid, 'plant_active_circuits_total'].value_counts().sort_index().rename_axis('active_circuits').reset_index(name='sample_count')
    ch['hours'] = ch.sample_count * dt
    heat = d.Heating_energy_kWh.sum(min_count=1) / 1000
    cool = d.Cooling_energy_kWh.sum(min_count=1) / 1000
    mheat = d.loc[d.Heating_load_source.eq('measured'), 'Heating_energy_kWh'].sum(min_count=1) / 1000
    mcool = d.loc[d.Cooling_load_source.eq('measured'), 'Cooling_energy_kWh'].sum(min_count=1) / 1000
    vheat = d.loc[valid, 'Heating_energy_kWh'].sum(min_count=1)
    vcool = d.loc[valid, 'Cooling_energy_kWh'].sum(min_count=1)
    hel = pd.to_numeric(d.loc[valid, 'plant_heating_power_kW'], errors='coerce').sum(min_count=1) * dt
    cel = pd.to_numeric(d.loc[valid, 'plant_cooling_power_kW'], errors='coerce').sum(min_count=1) * dt
    vel = d.loc[valid, 'Plant_electricity_kWh'].sum(min_count=1)
    summary = pd.DataFrame([{'metric': 'Study duration', 'value': (pd.Timestamp(c.ANNUAL_END_DATE_EXCLUSIVE) - pd.Timestamp(c.ANNUAL_START_DATE)).total_seconds() / 86400, 'unit': 'days'}, {'metric': 'Heating thermal demand total', 'value': heat, 'unit': 'MWh_th'}, {'metric': 'Heating measured contribution', 'value': mheat, 'unit': 'MWh_th'}, {'metric': 'Heating reconstructed contribution', 'value': heat - mheat, 'unit': 'MWh_th'}, {'metric': 'Cooling thermal demand total', 'value': cool, 'unit': 'MWh_th'}, {'metric': 'Cooling measured contribution', 'value': mcool, 'unit': 'MWh_th'}, {'metric': 'Cooling reconstructed contribution', 'value': cool - mcool, 'unit': 'MWh_th'}, {'metric': 'HERA modeled electricity on valid points', 'value': vel / 1000, 'unit': 'MWh_el'}, {'metric': 'Heating building-specific modeled SPF on valid points', 'value': vheat / hel if hel > 0 else np.nan, 'unit': '-'}, {'metric': 'Cooling building-specific modeled EER on valid points', 'value': vcool / cel if cel > 0 else np.nan, 'unit': '-'}, {'metric': 'Model-valid timestamp coverage', 'value': 100 * valid.mean(), 'unit': '%'}, {'metric': 'Model-domain unavailable duration', 'value': (~valid).sum() * dt, 'unit': 'h'}])
    comp = pd.DataFrame()
    if tab.table_exists(INPUT_STANDARDIZED_SUMMARY):
        st = tab.read_table(INPUT_STANDARDIZED_SUMMARY)
        rows = []
        for mode, bval in [('heating', vheat / hel if hel > 0 else np.nan), ('cooling', vcool / cel if cel > 0 else np.nan)]:
            q = st[st['mode'].astype(str).str.lower().eq(mode) & st['scope'].astype(str).eq('three_HERA_plant')]
            if not q.empty:
                rows.append({'mode': mode, 'standardized_index_name': q.iloc[0]['seasonal_index_name'], 'standardized_active_mode_index': q.iloc[0]['active_mode_seasonal_index'], 'building_specific_available_period_index': bval, 'same_metric_definition': False, 'note': 'Standardized bin index and building-specific available-period model result are intentionally separate.'})
        comp = pd.DataFrame(rows)
    for df, path, sheet in [(trends, OUTPUT_RECONSTRUCTION_TRENDS, 'Trends'), (schedules, OUTPUT_SCHEDULE_FACTORS, 'Schedule'), (cross, OUTPUT_CROSS_VALIDATION, 'CrossValidation'), (monthly, OUTPUT_MONTHLY, 'Monthly'), (hh, OUTPUT_ACTIVE_HERA_HOURS, 'HERAHours'), (ch, OUTPUT_ACTIVE_CIRCUIT_HOURS, 'CircuitHours'), (summary, OUTPUT_SUMMARY, 'Summary')]:
        tab.write_table(df, path, export_csv=c.EXPORT_CSV, export_xlsx=c.EXPORT_XLSX, csv_separator=c.CSV_SEPARATOR, csv_decimal=c.CSV_DECIMAL, float_format=c.CSV_FLOAT_FORMAT, sheet_name=sheet)
    tab.write_table(d, OUTPUT_5MIN, export_csv=True, export_xlsx=False, csv_separator=c.CSV_SEPARATOR, csv_decimal=c.CSV_DECIMAL, float_format=c.CSV_FLOAT_FORMAT, sheet_name='Annual5min')
    if not comp.empty:
        tab.write_table(comp, OUTPUT_STANDARD_COMPARISON, export_csv=c.EXPORT_CSV, export_xlsx=c.EXPORT_XLSX, csv_separator=c.CSV_SEPARATOR, csv_decimal=c.CSV_DECIMAL, float_format=c.CSV_FLOAT_FORMAT, sheet_name='Comparison')
    pass
if __name__ == '__main__':
    main()
