"""
02_clean_kiona_detailed.py

Combines one or more detailed Kiona 5-minute CSV exports and renames the long
machine tags to stable short column names. No filtering and no plots are done
here.
"""

# ============================================================
# 1. IMPORTS
# ============================================================

from pathlib import Path
import csv
import importlib.util
import sys
import pandas as pd
import numpy as np


# ============================================================
# 2. FILES USED BY THIS SCRIPT
#    CHANGE THE FOLDER/GLOB HERE IF NEW FILES ARE NAMED DIFFERENTLY
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = PROJECT_ROOT / "00_CONFIG" / "config.py"
KIONA_TAG_FILE = PROJECT_ROOT / "00_CONFIG" / "kiona_tags.py"
TABLE_IO_FILE = PROJECT_ROOT / "00_CONFIG" / "table_io.py"

INPUT_KIONA_FOLDER = PROJECT_ROOT / "01_RAW_DATA" / "Kiona"
INPUT_FILE_GLOB = "Kiona_Detailed_*.csv"
OUTPUT_CLEAN_DATA = PROJECT_ROOT / "02_PROCESSED_DATA" / "kiona_detailed_clean"


# ============================================================
# 3. CHANGEABLE SETTINGS
# ============================================================

KEEP_UNMAPPED_RAW_COLUMNS = False


# ============================================================
# 4. MODULE LOADING
# ============================================================

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

config = load_module("thesis_config_kiona_clean", CONFIG_FILE)
tags = load_module("kiona_tags_clean", KIONA_TAG_FILE)
table_io = load_module("table_io_kiona_clean", TABLE_IO_FILE)


# ============================================================
# 5. KIONA CSV READER
# ============================================================

def split_semicolon(line):
    return next(csv.reader([line], delimiter=";"))


def looks_like_machine_header(cells):
    n = sum(str(c).strip().startswith("SH_") for c in cells)
    return n >= 5


def read_kiona_csv(path):
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    header_idx = None
    for i, line in enumerate(lines[:10]):
        cells = split_semicolon(line)
        if looks_like_machine_header(cells):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(f"Could not find machine-tag header in {path.name}")

    df = pd.read_csv(path, sep=";", decimal=",", skiprows=header_idx, header=0, encoding="utf-8-sig")
    if not df.empty:
        first = str(df.iloc[0, 0]).strip()
        if pd.isna(pd.to_datetime(first, errors="coerce")):
            df = df.iloc[1:].reset_index(drop=True)

    timestamp_col = df.columns[0]
    df = df.rename(columns={timestamp_col: "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df[df["timestamp"].notna()].copy()
    for c in df.columns:
        if c != "timestamp":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


# ============================================================
# 6. STANDARDIZE COLUMNS
# ============================================================

def main():
    files = sorted(INPUT_KIONA_FOLDER.glob(INPUT_FILE_GLOB))
    if not files:
        raise FileNotFoundError(
            f"No files matched {INPUT_FILE_GLOB} in {INPUT_KIONA_FOLDER}.\n"
            "Recommended current filename: Kiona_Detailed_5min_2026.csv"
        )

    parts = [read_kiona_csv(path) for path in files]
    raw = pd.concat(parts, ignore_index=True, sort=False)
    raw = raw.sort_values("timestamp").drop_duplicates("timestamp", keep="last").reset_index(drop=True)

    rename = {tags.OUTDOOR_TAG: "outdoor_temp_C"}
    for unit, mapping in tags.UNIT_TAGS.items():
        for short, machine in mapping.items():
            standardized = f"HP{unit}_{short}"
            rename[machine] = standardized

    available = {k:v for k,v in rename.items() if k in raw.columns}
    if KEEP_UNMAPPED_RAW_COLUMNS:
        clean = raw.rename(columns=available)
    else:
        cols = ["timestamp"] + list(available.keys())
        clean = raw[[c for c in cols if c in raw.columns]].rename(columns=available)

    source_files = "; ".join(path.name for path in files)
    clean.insert(1, "source_files", source_files)

    table_io.write_table(clean, OUTPUT_CLEAN_DATA, export_csv=config.EXPORT_CSV, export_xlsx=False, csv_separator=config.CSV_SEPARATOR, csv_decimal=config.CSV_DECIMAL, float_format=config.CSV_FLOAT_FORMAT, sheet_name="Clean")



if __name__ == "__main__":
    main()
