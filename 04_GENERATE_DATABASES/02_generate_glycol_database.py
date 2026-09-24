"""
02_generate_glycol_database.py

Creates one reusable water/glycol property database. No plots are created here.
"""

# ============================================================
# 1. IMPORTS
# ============================================================

from pathlib import Path
import importlib.util
import sys
import numpy as np
import pandas as pd


# ============================================================
# 2. FILES USED BY THIS SCRIPT
#    CHANGE THESE PATHS HERE IF A DIFFERENT FILE IS USED
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = PROJECT_ROOT / "00_CONFIG" / "config.py"
GLYCOL_MODEL_FILE = PROJECT_ROOT / "03_MODELS" / "glycol_model.py"
TABLE_IO_FILE = PROJECT_ROOT / "00_CONFIG" / "table_io.py"

INPUT_GLYCOL_WORKBOOK = (
    PROJECT_ROOT / "01_RAW_DATA" / "Glycol" / "DOWCAL200E_Property_Tables_20-50vol.xlsx"
)

OUTPUT_PROPERTY_DATABASE = (
    PROJECT_ROOT / "06_RESULTS" / "databases" / "glycol_property_database"
)
OUTPUT_PROPERTY_METADATA = (
    PROJECT_ROOT / "06_RESULTS" / "databases" / "glycol_property_database_metadata"
)


# ============================================================
# 3. CHANGEABLE SETTINGS
# ============================================================

USE_SOURCE_TEMPERATURE_ROWS_ONLY = False


# ============================================================
# 4. MODULE LOADING
# ============================================================

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

config = load_module("thesis_config_glycol", CONFIG_FILE)
glycol = load_module("glycol_model_v2", GLYCOL_MODEL_FILE)
table_io = load_module("table_io_glycol", TABLE_IO_FILE)


# ============================================================
# 5. GENERATE DATABASE
# ============================================================

def main():
    if not INPUT_GLYCOL_WORKBOOK.exists():
        raise FileNotFoundError(
            f"Place/rename the glycol workbook as:\n{INPUT_GLYCOL_WORKBOOK}"
        )

    tables = glycol.load_property_workbook(INPUT_GLYCOL_WORKBOOK)
    rows = []

    for concentration in config.GLYCOL_CONCENTRATIONS_VOL_PERCENT:
        if concentration == 0:
            temperatures = np.arange(
                max(0.0, config.GLYCOL_TEMPERATURE_MIN_C),
                config.GLYCOL_TEMPERATURE_MAX_C + 0.5*config.GLYCOL_TEMPERATURE_STEP_K,
                config.GLYCOL_TEMPERATURE_STEP_K,
            )
        elif concentration in tables:
            if USE_SOURCE_TEMPERATURE_ROWS_ONLY:
                temperatures = tables[concentration]["temperature_C"].to_numpy(float)
            else:
                low = max(config.GLYCOL_TEMPERATURE_MIN_C, tables[concentration]["temperature_C"].min())
                high = min(config.GLYCOL_TEMPERATURE_MAX_C, tables[concentration]["temperature_C"].max())
                temperatures = np.arange(low, high + 0.5*config.GLYCOL_TEMPERATURE_STEP_K, config.GLYCOL_TEMPERATURE_STEP_K)
        else:
            continue

        for T in temperatures:
            p = glycol.interpolate_glycol_properties(tables, int(concentration), float(T))
            if p is None:
                continue
            p["source_workbook"] = INPUT_GLYCOL_WORKBOOK.name
            rows.append(p)

    database = pd.DataFrame(rows).sort_values(["concentration_vol_percent", "temperature_C"])
    table_io.write_table(
        database,
        OUTPUT_PROPERTY_DATABASE,
        export_csv=config.EXPORT_CSV,
        export_xlsx=config.EXPORT_XLSX,
        csv_separator=config.CSV_SEPARATOR,
        csv_decimal=config.CSV_DECIMAL,
        float_format=config.CSV_FLOAT_FORMAT,
        sheet_name="Properties",
    )

    metadata = pd.DataFrame([
        ["source_workbook", INPUT_GLYCOL_WORKBOOK.name, ""],
        ["concentrations_requested", ", ".join(map(str, config.GLYCOL_CONCENTRATIONS_VOL_PERCENT)), "vol-%"],
        ["rows_generated", len(database), "rows"],
        ["water_property_source", "IAPWS-IF97 Region 1", ""],
        ["glycol_extrapolation", "disabled", ""],
    ], columns=["item", "value", "unit"])
    table_io.write_table(metadata, OUTPUT_PROPERTY_METADATA, export_csv=config.EXPORT_CSV, export_xlsx=config.EXPORT_XLSX, csv_separator=config.CSV_SEPARATOR, csv_decimal=config.CSV_DECIMAL, float_format=config.CSV_FLOAT_FORMAT, sheet_name="Metadata")

    pass


if __name__ == "__main__":
    main()
