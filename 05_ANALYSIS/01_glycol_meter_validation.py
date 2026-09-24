"""
01_glycol_meter_validation.py

Recalculate the aligned OE thermal-power reference with 29 vol-% and 40 vol-%
DOWCAL 200E density/cp data.

Purpose
-------
The aligned Kiona workbook contains an OE glycol-concentration field of 29%,
while the installed system fluid is treated as 40 vol-% glycol in the thesis.
This script does not modify the source workbook. Instead, it re-evaluates the
same logged flow and delta-T rows with the dedicated 29% and 40% meter-
validation property tables and quantifies the resulting thermal-power shift.

Thermal power:
    Q = (Vdot_L_s / 1000) * rho(Tmean) * cp(Tmean) * deltaT

Outputs are intended as a meter/configuration validation diagnostic, not as a
replacement for the main glycol-property database.
"""

from pathlib import Path
import importlib.util
import sys

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONFIG_FILE = PROJECT_ROOT / "00_CONFIG" / "config.py"
TABLE_IO_FILE = PROJECT_ROOT / "00_CONFIG" / "table_io.py"

INPUT_ALIGNED_REFERENCE = (
    PROJECT_ROOT
    / "01_RAW_DATA"
    / "Kiona"
    / "Aligned_Reference"
    / "Kiona_OE_Validation_Aligned_29pct.xlsx"
)

INPUT_PROPERTY_29 = (
    PROJECT_ROOT
    / "01_RAW_DATA"
    / "Glycol"
    / "Meter_Validation"
    / "DOWCAL200E_29vol_Density_Cp.csv"
)

INPUT_PROPERTY_40 = (
    PROJECT_ROOT
    / "01_RAW_DATA"
    / "Glycol"
    / "Meter_Validation"
    / "DOWCAL200E_40vol_Density_Cp.csv"
)

OUTPUT_FOLDER = PROJECT_ROOT / "06_RESULTS" / "validation" / "glycol_meter"

UNIT_SHEETS = {
    1: "Unit1_OE401",
    2: "Unit2_OE402",
    3: "Unit3_OE403",
}

UNIT_LABELS = {
    1: "HP1 heating",
    2: "HP2 cooling",
    3: "HP3 cooling",
}


# ============================================================
# MODULE LOADING
# ============================================================

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


config = load_module("config_glycol_meter_validation", CONFIG_FILE)
table_io = load_module("table_io_glycol_meter_validation", TABLE_IO_FILE)


# ============================================================
# HELPERS
# ============================================================

def load_property_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)

    # The two meter-validation files intentionally preserve their original
    # decimal formatting, which is mixed between dot and comma. Read as text,
    # then normalize explicitly.
    data = pd.read_csv(path, sep=";", dtype=str)

    for column in ("temperature_C", "density_kg_m3", "cp_kJ_kgK"):
        data[column] = pd.to_numeric(
            data[column].astype(str).str.replace(",", ".", regex=False),
            errors="coerce",
        )

    data = data.dropna(
        subset=["temperature_C", "density_kg_m3", "cp_kJ_kgK"]
    ).sort_values("temperature_C")

    if len(data) < 2:
        raise ValueError(f"Insufficient property rows in {path}")

    return data


def interpolate_property(table: pd.DataFrame, temperatures, column: str):
    t = np.asarray(temperatures, dtype=float)
    xp = table["temperature_C"].to_numpy(dtype=float)
    fp = table[column].to_numpy(dtype=float)

    # Do not extrapolate beyond the dedicated validation table. Current aligned
    # data lie inside the -20...60 °C range, but retain NaN if that changes.
    values = np.interp(t, xp, fp)
    values[(t < xp.min()) | (t > xp.max()) | ~np.isfinite(t)] = np.nan
    return values


def export_table(dataframe: pd.DataFrame, name: str, sheet: str):
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    table_io.write_table(
        dataframe,
        OUTPUT_FOLDER / name,
        export_csv=config.EXPORT_CSV,
        export_xlsx=config.EXPORT_XLSX,
        csv_separator=config.CSV_SEPARATOR,
        csv_decimal=config.CSV_DECIMAL,
        float_format=config.CSV_FLOAT_FORMAT,
        sheet_name=sheet,
    )


# ============================================================
# CALCULATION
# ============================================================

def calculate_unit_rows(unit: int, sheet: str, prop29, prop40) -> pd.DataFrame:
    data = pd.read_excel(INPUT_ALIGNED_REFERENCE, sheet_name=sheet)

    required = [
        "Timestamp_local_5min",
        "OE_power_kW",
        "OE_flow_l_s",
        "OE_deltaT_K",
        "OE_T1_C",
        "OE_T2_C",
        "OE_glycol_percent",
    ]
    missing = [c for c in required if c not in data.columns]
    if missing:
        raise KeyError(f"{sheet}: missing column(s): {missing}")

    for column in required[1:]:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    out = pd.DataFrame({
        "timestamp_local_5min": data["Timestamp_local_5min"],
        "unit": unit,
        "unit_label": UNIT_LABELS[unit],
        "OE_meter": f"OE40{unit}",
        "aligned_reference_glycol_percent": data["OE_glycol_percent"],
        "logged_thermal_power_kW": data["OE_power_kW"],
        "flow_L_s": data["OE_flow_l_s"],
        "deltaT_K": data["OE_deltaT_K"],
        "T1_C": data["OE_T1_C"],
        "T2_C": data["OE_T2_C"],
    })

    out["mean_fluid_temperature_C"] = 0.5 * (out["T1_C"] + out["T2_C"])

    valid = (
        out["logged_thermal_power_kW"].notna()
        & out["flow_L_s"].notna()
        & out["deltaT_K"].notna()
        & out["mean_fluid_temperature_C"].notna()
        & (out["logged_thermal_power_kW"] > 0.0)
        & (out["flow_L_s"] > 0.0)
        & (out["deltaT_K"] > 0.0)
    )
    out = out.loc[valid].copy()

    T = out["mean_fluid_temperature_C"].to_numpy(dtype=float)

    for concentration, table in ((29, prop29), (40, prop40)):
        rho = interpolate_property(table, T, "density_kg_m3")
        cp = interpolate_property(table, T, "cp_kJ_kgK")
        q = (
            out["flow_L_s"].to_numpy(dtype=float)
            / 1000.0
            * rho
            * cp
            * out["deltaT_K"].to_numpy(dtype=float)
        )

        out[f"density_{concentration}vol_kg_m3"] = rho
        out[f"cp_{concentration}vol_kJ_kgK"] = cp
        out[f"recalculated_{concentration}vol_thermal_power_kW"] = q
        out[f"deviation_{concentration}vol_vs_logged_percent"] = (
            100.0
            * (q - out["logged_thermal_power_kW"].to_numpy(dtype=float))
            / out["logged_thermal_power_kW"].to_numpy(dtype=float)
        )

    out["40vol_minus_29vol_thermal_power_percent_of_29"] = (
        100.0
        * (
            out["recalculated_40vol_thermal_power_kW"]
            - out["recalculated_29vol_thermal_power_kW"]
        )
        / out["recalculated_29vol_thermal_power_kW"]
    )

    return out


def build_summary(rows: pd.DataFrame) -> pd.DataFrame:
    summary_rows = []

    for unit, g in rows.groupby("unit"):
        summary_rows.append({
            "unit": int(unit),
            "unit_label": UNIT_LABELS[int(unit)],
            "rows": int(len(g)),
            "mean_fluid_temperature_C": float(g["mean_fluid_temperature_C"].mean()),
            "mean_aligned_reference_glycol_percent": float(g["aligned_reference_glycol_percent"].mean()),
            "mean_deviation_29vol_vs_logged_percent": float(g["deviation_29vol_vs_logged_percent"].mean()),
            "mean_deviation_40vol_vs_logged_percent": float(g["deviation_40vol_vs_logged_percent"].mean()),
            "median_deviation_29vol_vs_logged_percent": float(g["deviation_29vol_vs_logged_percent"].median()),
            "median_deviation_40vol_vs_logged_percent": float(g["deviation_40vol_vs_logged_percent"].median()),
            "mean_40vol_minus_29vol_percent_of_29": float(g["40vol_minus_29vol_thermal_power_percent_of_29"].mean()),
        })

    return pd.DataFrame(summary_rows)


def main():
    for path in (INPUT_ALIGNED_REFERENCE, INPUT_PROPERTY_29, INPUT_PROPERTY_40):
        if not path.exists():
            raise FileNotFoundError(path)

    prop29 = load_property_table(INPUT_PROPERTY_29)
    prop40 = load_property_table(INPUT_PROPERTY_40)

    rows = pd.concat(
        [
            calculate_unit_rows(unit, sheet, prop29, prop40)
            for unit, sheet in UNIT_SHEETS.items()
        ],
        ignore_index=True,
    )

    summary = build_summary(rows)

    assumptions = pd.DataFrame([
        {
            "item": "aligned_reference_source",
            "value": str(INPUT_ALIGNED_REFERENCE.relative_to(PROJECT_ROOT)),
            "interpretation": "OE aligned reference workbook; its glycol field is nominally 29% for unit meters",
        },
        {
            "item": "29vol_property_source",
            "value": str(INPUT_PROPERTY_29.relative_to(PROJECT_ROOT)),
            "interpretation": "meter-validation density and cp table",
        },
        {
            "item": "40vol_property_source",
            "value": str(INPUT_PROPERTY_40.relative_to(PROJECT_ROOT)),
            "interpretation": "meter-validation density and cp table; thesis system fluid assumption",
        },
        {
            "item": "thermal_power_formula",
            "value": "Q_kW = flow_L_s/1000 * rho_kg_m3 * cp_kJ_kgK * deltaT_K",
            "interpretation": "recalculates thermal power from the same aligned OE flow and delta-T",
        },
        {
            "item": "system_glycol_interpretation",
            "value": "40 vol-%",
            "interpretation": "actual system concentration used for thesis interpretation; 29% retained only as logged/reference-meter comparison",
        },
    ])

    export_table(rows, "01_aligned_reference_29_vs_40_rows", "Rows")
    export_table(summary, "02_aligned_reference_29_vs_40_summary", "Summary")
    export_table(assumptions, "03_aligned_reference_29_vs_40_method", "Method")

    pass
    pass


if __name__ == "__main__":
    main()
