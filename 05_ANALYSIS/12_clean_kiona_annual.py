"""
12_clean_kiona_annual.py

Clean the long annual Kiona building export.

This script only performs raw-data preparation:
- reads and merges all annual Kiona CSV exports matching the configured glob;
- standardizes signal names;
- removes known frozen pre-logging placeholder periods by setting them to NaN;
- de-duplicates overlapping timestamps, keeping the later-file value;
- writes one reusable canonical processed annual dataset.

No heating/cooling mode interpretation and no plots are created here.
"""


# ============================================================
# 1. IMPORTS
# ============================================================

from pathlib import Path
import csv, importlib.util, sys
import numpy as np, pandas as pd


# ============================================================
# 2. FILES USED BY THIS SCRIPT
#    CHANGE THESE PATHS HERE IF A DIFFERENT FILE IS USED
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = PROJECT_ROOT / '00_CONFIG' / 'config.py'
TABLE_IO_FILE = PROJECT_ROOT / '00_CONFIG' / 'table_io.py'
INPUT_ANNUAL_KIONA_FOLDER = PROJECT_ROOT / '01_RAW_DATA' / 'Kiona'
OUTPUT_CLEAN = PROJECT_ROOT / '02_PROCESSED_DATA' / 'kiona_annual_clean'


# ============================================================
# 3. ANNUAL SIGNAL NAME MAP
# ============================================================

CLEAN_NAMES = {'SH_320001_RT503_MV': 'RT503_C', 'SH_320001_RT403_SPK': 'Heating_setpoint_C', 'SH_320001_RT403_MV': 'RT403_C', 'SH_320001_RT404_SPK': 'Ventilation_setpoint_C', 'SH_320001_RT404_MV': 'RT404_C', 'SH_320001_OE405_VS_PV': 'OE405_flow_L_s', 'SH_320001_OE405_RE_PV': 'OE405_thermal_power_kW', 'SH_320001_OE405_DT_PV': 'OE405_dT_K', 'SH_320001_OE404_DT_PV': 'OE404_dT_K', 'SH_320001_OE404_RE_PV': 'OE404_thermal_power_kW', 'SH_320001_OE404_RT511_PV': 'OE404_trip_C', 'SH_320001_OE404_VS_PV': 'OE404_flow_L_s', 'SH_320001_OE404_RT411_PV': 'OE404_return_C', 'SH_320001_RT504_MV': 'RT504_C', 'SH_320001_RT090_MV': 'Outdoor_C'}



# ============================================================
# 4. MODULE LOADING
# ============================================================

def load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    sys.modules[name] = m
    s.loader.exec_module(m)
    return m
config = load('cfg_annclean', CONFIG_FILE)
table_io = load('tab_annclean', TABLE_IO_FILE)



# ============================================================
# 5. RAW KIONA READER
# ============================================================

def read_raw(path):
    if not path.exists():
        raise FileNotFoundError(path)
    lines = path.read_text(encoding='utf-8-sig', errors='replace').splitlines()
    header = 0
    for i, line in enumerate(lines[:10]):
        cells = next(csv.reader([line], delimiter=';'))
        if sum((str(c).strip().startswith('SH_') for c in cells)) >= 5:
            header = i
            break
    d = pd.read_csv(path, sep=';', decimal=',', skiprows=header, header=0, encoding='utf-8-sig')
    d = d.rename(columns={d.columns[0]: 'timestamp'})
    d['timestamp'] = pd.to_datetime(d['timestamp'], errors='coerce')
    d = d[d['timestamp'].notna()].copy()
    for c in d.columns:
        if c != 'timestamp':
            d[c] = pd.to_numeric(d[c], errors='coerce')
    return d.sort_values('timestamp').drop_duplicates('timestamp', keep='last').reset_index(drop=True)



# ============================================================
# 6. CLEANING AND EXPORT
# ============================================================

def load_annual_raw_exports():
    paths = sorted(INPUT_ANNUAL_KIONA_FOLDER.glob(config.ANNUAL_RAW_GLOB))
    if not paths:
        raise FileNotFoundError(
            f"No annual Kiona raw files matching {config.ANNUAL_RAW_GLOB!r} "
            f"were found in {INPUT_ANNUAL_KIONA_FOLDER}."
        )

    frames = [read_raw(path) for path in paths]
    raw = pd.concat(frames, ignore_index=True, sort=False)
    return (
        raw.sort_values('timestamp', kind='stable')
        .drop_duplicates('timestamp', keep='last')
        .reset_index(drop=True)
    )


def main():
    raw = load_annual_raw_exports()
    start = raw.timestamp.min()
    clean = pd.DataFrame({'timestamp': raw.timestamp})
    for tag, name in CLEAN_NAMES.items():
        if tag not in raw.columns:
            clean[name] = np.nan
            continue
        s = pd.to_numeric(raw[tag], errors='coerce').copy()
        vf = pd.Timestamp(config.ANNUAL_SIGNAL_VALID_FROM.get(tag, start))
        s.loc[raw.timestamp < vf] = np.nan
        clean[name] = s
    table_io.write_table(clean, OUTPUT_CLEAN, export_csv=True, export_xlsx=False, csv_separator=config.CSV_SEPARATOR, csv_decimal=config.CSV_DECIMAL, float_format=config.CSV_FLOAT_FORMAT, sheet_name='Clean')
if __name__ == '__main__':
    main()
