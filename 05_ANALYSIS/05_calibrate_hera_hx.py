"""
05_calibrate_hera_hx.py

Creates the compact field-calibration table used by the reusable HERA model.
No plots are created here.
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
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = PROJECT_ROOT / "00_CONFIG" / "config.py"
TABLE_IO_FILE = PROJECT_ROOT / "00_CONFIG" / "table_io.py"
INPUT_STABLE_PERIODS = PROJECT_ROOT / "02_PROCESSED_DATA" / "kiona_stable_periods.csv"
INPUT_VALIDATION_ROWS = PROJECT_ROOT / "06_RESULTS" / "validation" / "validation_rows.csv"
OUTPUT_CALIBRATION = PROJECT_ROOT / "06_RESULTS" / "databases" / "hera_hx_calibration"
OUTPUT_CALIBRATION_POINTS = PROJECT_ROOT / "06_RESULTS" / "validation" / "hera_hx_calibration_points"


# ============================================================
# 3. CHANGEABLE SETTINGS
# ============================================================

MIN_CIRCUIT_POINTS_TO_ACCEPT_FIELD_CALIBRATION = 5
EXPORT_CALIBRATION_POINTS = True


# ============================================================
# 4. MODULE LOADING
# ============================================================

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

config = load_module("thesis_config_hxcal", CONFIG_FILE)
table_io = load_module("table_io_hxcal", TABLE_IO_FILE)


# ============================================================
# 5. CALIBRATION
# ============================================================

def main():
    stable = table_io.read_table(INPUT_STABLE_PERIODS)
    validation = table_io.read_table(INPUT_VALIDATION_ROWS)
    small = stable[["stable_period_id", "mean_outdoor_temp_C", "mean_hot_side_out_C"]].drop_duplicates("stable_period_id")
    merged = validation.merge(small, on="stable_period_id", how="inner")

    points = []
    for _, r in merged.iterrows():
        if str(r.get("model_status", "")) != "OK":
            continue
        mode = str(r.get("mode", "")).lower()
        if mode not in {"heating", "cooling"}:
            continue
        outdoor = pd.to_numeric(pd.Series([r.get("mean_outdoor_temp_C")]), errors="coerce").iloc[0]
        water_out = pd.to_numeric(pd.Series([r.get("mean_hot_side_out_C")]), errors="coerce").iloc[0]
        for c in (1,2):
            if not bool(r.get(f"c{c}_active", False)):
                continue
            te = pd.to_numeric(pd.Series([r.get(f"c{c}_T_evap_sat_C")]), errors="coerce").iloc[0]
            tc = pd.to_numeric(pd.Series([r.get(f"c{c}_T_cond_sat_C")]), errors="coerce").iloc[0]
            qev = pd.to_numeric(pd.Series([r.get(f"c{c}_frascold_Q_evap_kW")]), errors="coerce").iloc[0]
            qco = pd.to_numeric(pd.Series([r.get(f"c{c}_frascold_Q_cond_kW")]), errors="coerce").iloc[0]
            if not all(np.isfinite(v) for v in [outdoor, water_out, te, tc, qev, qco]):
                continue

            if mode == "heating":
                qair, qwater = qev, qco
                air_app = outdoor-te
                water_app = tc-water_out
            else:
                qair, qwater = qco, qev
                air_app = tc-outdoor
                water_app = water_out-te
            if air_app <= 0.5 or water_app <= 0.5:
                continue

            # Validation does not use unreliable fan-start tags. For calibration,
            # normalize with the already established reference fan fraction.
            fan_fraction = config.HERA_FALLBACK_CALIBRATION[mode]["reference_fan_speed_fraction"]
            ua_air_obs = qair/air_app
            ua_air_100 = ua_air_obs / fan_fraction**config.AIR_HT_EXPONENT
            ua_water = qwater/water_app
            points.append({
                "stable_period_id": r["stable_period_id"],
                "unit": r.get("unit", np.nan),
                "mode": mode,
                "circuit": c,
                "outdoor_C": outdoor,
                "water_out_C": water_out,
                "T_evap_C": te,
                "T_cond_C": tc,
                "Qair_kW": qair,
                "Qwater_kW": qwater,
                "air_approach_K": air_app,
                "water_approach_K": water_app,
                "fan_speed_fraction_reference": fan_fraction,
                "UA_air_100_kW_K": ua_air_100,
                "UA_water_kW_K": ua_water,
            })

    points = pd.DataFrame(points)
    summary = []
    for mode in ["heating", "cooling"]:
        g = points[points["mode"] == mode] if not points.empty else pd.DataFrame()
        fallback = config.HERA_FALLBACK_CALIBRATION[mode]
        if len(g) >= MIN_CIRCUIT_POINTS_TO_ACCEPT_FIELD_CALIBRATION:
            summary.append({
                "mode": mode,
                "source": "field calibration from Kiona stable periods + validation",
                "n_circuit_points": len(g),
                "air_UA_100_kW_K": g["UA_air_100_kW_K"].median(),
                "water_UA_ref_kW_K": g["UA_water_kW_K"].median(),
                "reference_air_approach_K": g["air_approach_K"].median(),
                "reference_water_approach_K": g["water_approach_K"].median(),
                "reference_fan_speed_fraction": fallback["reference_fan_speed_fraction"],
            })
        else:
            summary.append({
                "mode": mode,
                "source": "fallback from previously validated analytical model",
                "n_circuit_points": len(g),
                "air_UA_100_kW_K": fallback["air_UA_100_kW_K"],
                "water_UA_ref_kW_K": fallback["water_UA_kW_K"],
                "reference_air_approach_K": fallback["reference_air_approach_K"],
                "reference_water_approach_K": fallback["reference_water_approach_K"],
                "reference_fan_speed_fraction": fallback["reference_fan_speed_fraction"],
            })

    summary = pd.DataFrame(summary)
    table_io.write_table(summary, OUTPUT_CALIBRATION, export_csv=config.EXPORT_CSV, export_xlsx=config.EXPORT_XLSX, csv_separator=config.CSV_SEPARATOR, csv_decimal=config.CSV_DECIMAL, float_format=config.CSV_FLOAT_FORMAT, sheet_name="Calibration")
    if EXPORT_CALIBRATION_POINTS:
        table_io.write_table(points, OUTPUT_CALIBRATION_POINTS, export_csv=config.EXPORT_CSV, export_xlsx=config.EXPORT_XLSX, csv_separator=config.CSV_SEPARATOR, csv_decimal=config.CSV_DECIMAL, float_format=config.CSV_FLOAT_FORMAT, sheet_name="Points")
    pass


if __name__ == "__main__":
    main()
