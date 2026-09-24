"""
03_filter_kiona_stable_periods.py

Stable operating-period filter for the standardized detailed Kiona dataset.
Known-bad fan-start signals are not used for circuit-activity classification.
Runtime counters are preferred when informative; pressure lift is the fallback.
No plots are produced here.
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
TABLE_IO_FILE = PROJECT_ROOT / "00_CONFIG" / "table_io.py"
INPUT_CLEAN_KIONA = PROJECT_ROOT / "02_PROCESSED_DATA" / "kiona_detailed_clean.csv"

OUTPUT_STABLE_PERIODS = PROJECT_ROOT / "02_PROCESSED_DATA" / "kiona_stable_periods"
OUTPUT_FILTER_SUMMARY = PROJECT_ROOT / "06_RESULTS" / "validation" / "kiona_filter_summary"
OUTPUT_FILTERED_ROWS = PROJECT_ROOT / "06_RESULTS" / "validation" / "kiona_filtered_rows"


# ============================================================
# 3. CHANGEABLE OUTPUT SETTINGS
# ============================================================

EXPORT_FILTERED_TIMESTAMP_ROWS = False
EXPORT_SHORT_STABLE_RUNS = False

UNIT_MODE = {1: "heating", 2: "cooling"}


# ============================================================
# 4. MODULE LOADING
# ============================================================

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

config = load_module("thesis_config_kiona_filter", CONFIG_FILE)
table_io = load_module("table_io_kiona_filter", TABLE_IO_FILE)


# ============================================================
# 5. R290 SATURATION TEMPERATURE
# ============================================================

def propane_sat_temp_from_abs_bar(p_abs_bar):
    p = np.asarray(p_abs_bar, dtype=float)
    out = np.full(p.shape, np.nan, dtype=float)
    valid = np.isfinite(p) & (p > 0)
    if not np.any(valid):
        return out
    logp = np.log10(p[valid])
    A1, B1, C1 = 3.98292, 819.296, -24.417
    T = B1/(A1-logp)-C1
    high = T > 320.7
    if np.any(high):
        A2, B2, C2 = 4.53678, 1149.36, 24.906
        T[high] = B2/(A2-logp[high])-C2
    out[valid] = T-273.15
    return out


# ============================================================
# 6. FILTER HELPERS
# ============================================================

def rolling_std(series, window):
    return series.rolling(window, center=True, min_periods=window).std()


def rolling_state_constant(series_bool, window):
    x = series_bool.astype(int)
    return (
        x.rolling(window, center=True, min_periods=window).min()
        == x.rolling(window, center=True, min_periods=window).max()
    )


def activity_from_runtime_or_pressure(d, unit, circuit):
    """Classify circuit state from refrigerant pressure lift.

    The compressor operating-time counters in the Kiona export are cumulative
    counters that update only intermittently. A zero 5-minute counter delta
    therefore does NOT mean that a compressor was off during that sample.

    Stable-period activity is consequently based on the directly observed
    refrigerant pressure lift. Runtime-counter increments are retained only as
    supporting diagnostic evidence.

    Known-bad fan/start signals are not used.
    """
    runtime_col = f"HP{unit}_runtime_counter_c{circuit}"

    p_evap = pd.to_numeric(
        d[f"HP{unit}_evaporating_pressure_c{circuit}_bar"],
        errors="coerce",
    )

    p_cond = pd.to_numeric(
        d[f"HP{unit}_condensing_pressure_c{circuit}_bar"],
        errors="coerce",
    )

    lift = p_cond - p_evap

    active = (
        lift
        >= config.KIONA_PRESSURE_LIFT_ACTIVE_BAR
    )

    if runtime_col in d.columns:
        runtime = pd.to_numeric(
            d[runtime_col],
            errors="coerce",
        )

        runtime_increment = (
            runtime.diff()
            > 0
        )

        basis = np.where(
            active & runtime_increment,
            "pressure lift; runtime-counter increment confirms activity",
            np.where(
                active,
                "pressure lift",
                "inactive",
            ),
        )
    else:
        basis = np.where(
            active,
            "pressure lift",
            "inactive",
        )

    return (
        active.fillna(False),
        lift,
        basis,
    )


def process_unit(raw, unit):
    prefix = f"HP{unit}_"
    needed = [
        "timestamp", "outdoor_temp_C",
        prefix+"electrical_power_kW", prefix+"working_setpoint", prefix+"capacity_request_percent",
        prefix+"hot_side_in_C", prefix+"hot_side_out_C",
    ]
    for c in (1,2):
        needed += [
            prefix+f"suction_temp_c{c}_C", prefix+f"condensing_pressure_c{c}_bar",
            prefix+f"evaporating_pressure_c{c}_bar", prefix+f"superheat_c{c}_K",
        ]
        runtime = prefix+f"runtime_counter_c{c}"
        if runtime in raw.columns:
            needed.append(runtime)

    missing = [c for c in needed if c not in raw.columns]
    if missing:
        raise KeyError(f"HP{unit} clean Kiona data is missing: {missing}")

    d = raw[needed].copy()
    d.insert(1, "unit", unit)
    d.insert(2, "mode", UNIT_MODE[unit])
    rename = {c: c[len(prefix):] for c in d.columns if c.startswith(prefix)}
    d = d.rename(columns=rename)

    d["gap_prev_min"] = d["timestamp"].diff().dt.total_seconds()/60.0
    d["gap_next_min"] = -d["timestamp"].diff(-1).dt.total_seconds()/60.0
    d["timestamp_continuity_pass"] = (
        d["gap_prev_min"].fillna(5.0) <= config.KIONA_MAX_TIMESTAMP_GAP_MIN
    ) & (
        d["gap_next_min"].fillna(5.0) <= config.KIONA_MAX_TIMESTAMP_GAP_MIN
    )

    for c in (1,2):
        active, lift, basis = activity_from_runtime_or_pressure(raw, unit, c)
        d[f"c{c}_active"] = active.to_numpy()
        d[f"pressure_lift_c{c}_bar"] = lift.to_numpy()
        d[f"c{c}_activity_basis"] = basis
        p_evap_abs = d[f"evaporating_pressure_c{c}_bar"] + config.ATMOSPHERIC_PRESSURE_BAR
        p_cond_abs = d[f"condensing_pressure_c{c}_bar"] + config.ATMOSPHERIC_PRESSURE_BAR
        d[f"evap_sat_temp_c{c}_C"] = propane_sat_temp_from_abs_bar(p_evap_abs)
        d[f"cond_sat_temp_c{c}_C"] = propane_sat_temp_from_abs_bar(p_cond_abs)
        d[f"evap_air_approach_c{c}_K"] = d["outdoor_temp_C"] - d[f"evap_sat_temp_c{c}_C"]
        d[f"cond_hot_side_approach_c{c}_K"] = d[f"cond_sat_temp_c{c}_C"] - d["hot_side_out_C"]

    d["active_circuit_count"] = d["c1_active"].astype(int)+d["c2_active"].astype(int)
    d["unit_running_pass"] = (
        (d["electrical_power_kW"] >= config.KIONA_MIN_ELECTRICAL_POWER_KW)
        & (d["capacity_request_percent"] >= config.KIONA_MIN_CAPACITY_REQUEST_PERCENT)
        & (d["active_circuit_count"] >= 1)
    )
    d["c1_state_stable_pass"] = rolling_state_constant(d["c1_active"], config.KIONA_STABLE_WINDOW_ROWS)
    d["c2_state_stable_pass"] = rolling_state_constant(d["c2_active"], config.KIONA_STABLE_WINDOW_ROWS)

    thresholds = {
        "electrical_power_kW": config.KIONA_MAX_PEL_STD_KW,
        "capacity_request_percent": config.KIONA_MAX_CAPACITY_REQUEST_STD_PERCENT,
        "working_setpoint": config.KIONA_MAX_SETPOINT_STD_K,
        "hot_side_in_C": config.KIONA_MAX_HOT_SIDE_TEMP_STD_K,
        "hot_side_out_C": config.KIONA_MAX_HOT_SIDE_TEMP_STD_K,
        "outdoor_temp_C": config.KIONA_MAX_OUTDOOR_STD_K,
    }
    pass_cols = ["timestamp_continuity_pass", "unit_running_pass", "c1_state_stable_pass", "c2_state_stable_pass"]
    for col, threshold in thresholds.items():
        pc = f"stable_{col}_pass"
        d[pc] = rolling_std(d[col], config.KIONA_STABLE_WINDOW_ROWS) <= threshold
        pass_cols.append(pc)

    for c in (1,2):
        active = d[f"c{c}_active"]
        circ_thresholds = {
            f"evaporating_pressure_c{c}_bar": config.KIONA_MAX_EVAP_PRESSURE_STD_BAR,
            f"condensing_pressure_c{c}_bar": config.KIONA_MAX_COND_PRESSURE_STD_BAR,
            f"suction_temp_c{c}_C": config.KIONA_MAX_SUCTION_TEMP_STD_K,
            f"superheat_c{c}_K": config.KIONA_MAX_SUPERHEAT_STD_K,
        }
        for col, threshold in circ_thresholds.items():
            pc = f"stable_{col}_pass"
            d[pc] = (~active) | (rolling_std(d[col], config.KIONA_STABLE_WINDOW_ROWS) <= threshold)
            pass_cols.append(pc)

        if unit == 1:
            thermo = (
                (d[f"evap_air_approach_c{c}_K"] >= config.HP1_MIN_EVAP_AIR_APPROACH_K)
                & (d[f"cond_hot_side_approach_c{c}_K"] >= config.HP1_MIN_COND_WATER_APPROACH_K)
            )
            pc = f"c{c}_hp1_thermo_pass"
            d[pc] = (~active) | thermo
            pass_cols.append(pc)

    d["stable_row_pass"] = d[pass_cols].all(axis=1)
    return d


def summarize_periods(d, unit):
    stable = d["stable_row_pass"].fillna(False)
    break_gap = d["gap_prev_min"].fillna(5.0) > config.KIONA_MAX_TIMESTAMP_GAP_MIN
    group_id = ((stable != stable.shift(fill_value=False)) | break_gap).cumsum()
    rows = []
    shorts = []

    numeric_cols = [
        "electrical_power_kW", "capacity_request_percent", "working_setpoint", "outdoor_temp_C",
        "hot_side_in_C", "hot_side_out_C",
        "evaporating_pressure_c1_bar", "condensing_pressure_c1_bar", "superheat_c1_K", "suction_temp_c1_C",
        "evaporating_pressure_c2_bar", "condensing_pressure_c2_bar", "superheat_c2_K", "suction_temp_c2_C",
        "pressure_lift_c1_bar", "pressure_lift_c2_bar",
        "evap_sat_temp_c1_C", "cond_sat_temp_c1_C", "evap_sat_temp_c2_C", "cond_sat_temp_c2_C",
        "evap_air_approach_c1_K", "cond_hot_side_approach_c1_K", "evap_air_approach_c2_K", "cond_hot_side_approach_c2_K",
    ]

    for _, g in d[stable].groupby(group_id[stable]):
        n = len(g)
        c1, c2 = bool(g["c1_active"].all()), bool(g["c2_active"].all())
        row = {
            "unit": unit,
            "mode": UNIT_MODE[unit],
            "start_time": g["timestamp"].iloc[0],
            "end_time": g["timestamp"].iloc[-1],
            "n_5min_samples": n,
            "nominal_sample_coverage_minutes": 5*n,
            "c1_active": c1,
            "c2_active": c2,
            "active_configuration": "C1+C2" if c1 and c2 else "C1" if c1 else "C2" if c2 else "none",
        }
        for col in numeric_cols:
            row[f"mean_{col}"] = g[col].mean()
            row[f"std_{col}"] = g[col].std(ddof=1) if n > 1 else 0.0
            row[f"min_{col}"] = g[col].min()
            row[f"max_{col}"] = g[col].max()

        for c in (1,2):
            if row[f"c{c}_active"]:
                pe = row[f"mean_evaporating_pressure_c{c}_bar"] + config.ATMOSPHERIC_PRESSURE_BAR
                pc = row[f"mean_condensing_pressure_c{c}_bar"] + config.ATMOSPHERIC_PRESSURE_BAR
                row[f"mean_pressure_ratio_c{c}"] = pc/pe if pe > 0 else np.nan
            else:
                row[f"mean_pressure_ratio_c{c}"] = np.nan
        prs = [row["mean_pressure_ratio_c1"], row["mean_pressure_ratio_c2"]]
        prs = [v for v in prs if np.isfinite(v)]
        row["mean_active_pressure_ratio"] = float(np.mean(prs)) if prs else np.nan

        if n >= config.KIONA_MIN_STABLE_PERIOD_ROWS:
            rows.append(row)
        else:
            shorts.append(row)

    return pd.DataFrame(rows), pd.DataFrame(shorts)


# ============================================================
# 7. MAIN
# ============================================================

def main():
    raw = table_io.read_table(INPUT_CLEAN_KIONA)
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], errors="coerce")
    raw = raw[raw["timestamp"].notna()].sort_values("timestamp").reset_index(drop=True)

    all_periods, all_rows, all_shorts = [], [], []
    summary_rows = []
    for unit in (1,2):
        processed = process_unit(raw, unit)
        periods, shorts = summarize_periods(processed, unit)
        all_rows.append(processed)
        if not periods.empty:
            all_periods.append(periods)
        if not shorts.empty:
            all_shorts.append(shorts)
        summary_rows.append({
            "unit": unit,
            "mode": UNIT_MODE[unit],
            "input_rows": len(processed),
            "stable_rows": int(processed["stable_row_pass"].sum()),
            "accepted_periods": len(periods),
            "short_stable_runs": len(shorts),
        })

    stable = pd.concat(all_periods, ignore_index=True) if all_periods else pd.DataFrame()
    if not stable.empty:
        stable = stable.sort_values(["unit", "start_time"]).reset_index(drop=True)
        stable.insert(2, "stable_period_id", "")
        for unit in (1,2):
            idx = stable.index[stable["unit"] == unit]
            stable.loc[idx, "stable_period_id"] = [f"HP{unit}_{i+1:03d}" for i in range(len(idx))]

    summary = pd.DataFrame(summary_rows)
    table_io.write_table(stable, OUTPUT_STABLE_PERIODS, export_csv=config.EXPORT_CSV, export_xlsx=config.EXPORT_XLSX, csv_separator=config.CSV_SEPARATOR, csv_decimal=config.CSV_DECIMAL, float_format=config.CSV_FLOAT_FORMAT, sheet_name="StablePeriods")
    table_io.write_table(summary, OUTPUT_FILTER_SUMMARY, export_csv=config.EXPORT_CSV, export_xlsx=config.EXPORT_XLSX, csv_separator=config.CSV_SEPARATOR, csv_decimal=config.CSV_DECIMAL, float_format=config.CSV_FLOAT_FORMAT, sheet_name="Summary")

    if EXPORT_FILTERED_TIMESTAMP_ROWS:
        rows = pd.concat(all_rows, ignore_index=True)
        table_io.write_table(rows, OUTPUT_FILTERED_ROWS, export_csv=config.EXPORT_CSV, export_xlsx=False, csv_separator=config.CSV_SEPARATOR, csv_decimal=config.CSV_DECIMAL, float_format=config.CSV_FLOAT_FORMAT, sheet_name="Rows")
    if EXPORT_SHORT_STABLE_RUNS and all_shorts:
        shorts = pd.concat(all_shorts, ignore_index=True)
        table_io.write_table(shorts, OUTPUT_STABLE_PERIODS.parent/"kiona_short_stable_runs", export_csv=config.EXPORT_CSV, export_xlsx=config.EXPORT_XLSX, csv_separator=config.CSV_SEPARATOR, csv_decimal=config.CSV_DECIMAL, float_format=config.CSV_FLOAT_FORMAT, sheet_name="ShortRuns")

    pass


if __name__ == "__main__":
    main()
