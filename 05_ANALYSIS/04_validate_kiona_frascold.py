"""
04_validate_kiona_frascold.py

Validation analysis using the processed Kiona stable-period table and the
already-generated Frascold master database. No plots are generated here.
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
FRASCOLD_GRID_MODEL_FILE = PROJECT_ROOT / "03_MODELS" / "frascold_grid_model.py"

INPUT_KIONA_STABLE_PERIODS = PROJECT_ROOT / "02_PROCESSED_DATA" / "kiona_stable_periods.csv"
INPUT_FRASCOLD_DATABASE = PROJECT_ROOT / "06_RESULTS" / "databases" / "frascold_performance_grid.csv"

OUTPUT_VALIDATION_ROWS = PROJECT_ROOT / "06_RESULTS" / "validation" / "validation_rows"
OUTPUT_VALIDATION_SUMMARY = PROJECT_ROOT / "06_RESULTS" / "validation" / "validation_summary"
OUTPUT_VALIDATION_ASSUMPTIONS = PROJECT_ROOT / "06_RESULTS" / "validation" / "validation_assumptions"


# ============================================================
# 3. CHANGEABLE SETTINGS
# ============================================================

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

config = load_module("thesis_config_validation", CONFIG_FILE)
table_io = load_module("table_io_validation", TABLE_IO_FILE)
grid_module = load_module("frascold_grid_validation", FRASCOLD_GRID_MODEL_FILE)
FrascoldGridLookup = grid_module.FrascoldGridLookup


# ============================================================
# 5. THERMODYNAMIC / CONTROL HELPERS
# ============================================================

def propane_sat_temp_from_gauge_bar(p_gauge_bar):
    p_abs = float(p_gauge_bar) + config.ATMOSPHERIC_PRESSURE_BAR
    if not np.isfinite(p_abs) or p_abs <= 0:
        return np.nan
    logp = np.log10(p_abs)
    A1,B1,C1 = 3.98292,819.296,-24.417
    T = B1/(A1-logp)-C1
    if T > 320.7:
        A2,B2,C2 = 4.53678,1149.36,24.906
        T = B2/(A2-logp)-C2
    return float(T-273.15)


def provisional_frequency(capacity_request, active_count):
    demand = float(np.clip(capacity_request, 0.0, 100.0))
    command = min(100.0, 2.0*demand) if active_count == 1 else demand
    hz = np.clip(config.VALIDATION_COMMAND_TO_HZ*command, config.VALIDATION_MIN_FREQUENCY_HZ, config.VALIDATION_MAX_FREQUENCY_HZ)
    return float(command), float(hz)


def get_frequency(source, circuit, active_count):
    candidates = [
        f"mean_compressor_frequency_c{circuit}_Hz",
        f"mean_frequency_c{circuit}_Hz",
        f"compressor_frequency_c{circuit}_Hz",
    ]
    if config.VALIDATION_FREQUENCY_METHOD in {"auto", "measured"}:
        for col in candidates:
            if col in source.index:
                value = pd.to_numeric(pd.Series([source.get(col)]), errors="coerce").iloc[0]
                if np.isfinite(value):
                    return float(value), "measured Kiona frequency"
        if config.VALIDATION_FREQUENCY_METHOD == "measured":
            return np.nan, "measured frequency unavailable"

    demand = pd.to_numeric(pd.Series([source["mean_capacity_request_percent"]]), errors="coerce").iloc[0]
    _, hz = provisional_frequency(float(demand), active_count)
    return hz, "provisional capacity-request mapping"


def estimate_fan_power(capacity_request, active_count):
    if config.VALIDATION_FAN_METHOD == "rated_per_active_circuit":
        return active_count*config.FAN_RATED_POWER_PER_CIRCUIT_KW, "rated pair power per active circuit"
    demand = float(np.clip(capacity_request, 0.0, 100.0))
    speed = min(1.0, 2.0*demand/100.0) if active_count == 1 else demand/100.0
    return active_count*config.FAN_RATED_POWER_PER_CIRCUIT_KW*speed**3, "capacity-request proxy + cubic fan law"


def diagnostic_best_fit_frequency(fmap, circuit_conditions, target_compressor_power_kW):
    """Back-calculate a common compressor frequency for diagnostic plots only.

    This uses measured Kiona power and therefore is NOT a validation input. It
    is only used to test whether the provisional frequency reconstruction can
    explain part of the power residual.
    """
    if (
        not np.isfinite(target_compressor_power_kW)
        or target_compressor_power_kW <= 0
        or not circuit_conditions
    ):
        return np.nan, np.nan, "unavailable"

    candidates = np.linspace(
        config.VALIDATION_MIN_FREQUENCY_HZ,
        config.VALIDATION_MAX_FREQUENCY_HZ,
        161,
    )
    valid_f = []
    predicted_power = []

    for frequency in candidates:
        total = 0.0
        valid_point = True
        for te, tc in circuit_conditions:
            try:
                total += fmap.interpolate(
                    te, tc, float(frequency)
                )["compressor_power_kW"]
            except Exception:
                valid_point = False
                break

        if valid_point:
            valid_f.append(float(frequency))
            predicted_power.append(float(total))

    if not valid_f:
        return np.nan, np.nan, "no valid Frascold frequency"

    valid_f = np.asarray(valid_f, dtype=float)
    predicted_power = np.asarray(predicted_power, dtype=float)
    index = int(
        np.nanargmin(
            np.abs(predicted_power - target_compressor_power_kW)
        )
    )

    residual = predicted_power[index] - target_compressor_power_kW
    pmin = float(np.nanmin(predicted_power))
    pmax = float(np.nanmax(predicted_power))

    if target_compressor_power_kW < pmin:
        status = "target below 30-70 Hz map power"
    elif target_compressor_power_kW > pmax:
        status = "target above 30-70 Hz map power"
    else:
        status = "interior diagnostic match"

    return float(valid_f[index]), float(residual), status


# ============================================================
# 6. VALIDATION CALCULATION
# ============================================================

def main():
    stable = table_io.read_table(INPUT_KIONA_STABLE_PERIODS)
    fmap = FrascoldGridLookup(INPUT_FRASCOLD_DATABASE)
    rows = []

    for idx, source in stable.iterrows():
        unit = int(source["unit"])
        mode = str(source.get("mode", UNIT_MODE.get(unit, "unknown"))).lower()
        c1 = bool(source["c1_active"])
        c2 = bool(source["c2_active"])
        active_count = int(c1)+int(c2)
        measured = float(pd.to_numeric(pd.Series([source["mean_electrical_power_kW"]]), errors="coerce").iloc[0])
        demand = float(pd.to_numeric(pd.Series([source["mean_capacity_request_percent"]]), errors="coerce").iloc[0])
        fan_power, fan_method = estimate_fan_power(demand, active_count)

        out = {
            "stable_period_id": source.get("stable_period_id", f"row_{idx}"),
            "unit": unit,
            "mode": mode,
            "start_time": source.get("start_time", np.nan),
            "end_time": source.get("end_time", np.nan),
            "active_configuration": source.get("active_configuration", np.nan),
            "active_circuit_count": active_count,
            "capacity_request_percent": demand,
            "kiona_chiller_unit_electrical_power_kW": measured,
            "estimated_total_fan_power_kW": fan_power,
            "fan_power_method": fan_method,
            "model_status": "OK",
            "model_error": "",
        }

        predictions = []
        frequency_sources = []
        active_frequencies = []
        active_superheats = []
        circuit_conditions = []
        for circuit, active in [(1,c1),(2,c2)]:
            out[f"c{circuit}_active"] = active
            if not active:
                continue
            pe = float(source[f"mean_evaporating_pressure_c{circuit}_bar"])
            pc = float(source[f"mean_condensing_pressure_c{circuit}_bar"])
            te = propane_sat_temp_from_gauge_bar(pe)
            tc = propane_sat_temp_from_gauge_bar(pc)
            frequency, frequency_source = get_frequency(source, circuit, active_count)
            frequency_sources.append(frequency_source)
            if np.isfinite(frequency):
                active_frequencies.append(float(frequency))
            circuit_conditions.append((te, tc))

            measured_superheat = pd.to_numeric(
                pd.Series([source.get(f"mean_superheat_c{circuit}_K", np.nan)]),
                errors="coerce",
            ).iloc[0]
            if np.isfinite(measured_superheat):
                active_superheats.append(float(measured_superheat))

            out[f"c{circuit}_T_evap_sat_C"] = te
            out[f"c{circuit}_T_cond_sat_C"] = tc
            out[f"c{circuit}_frequency_Hz"] = frequency
            out[f"c{circuit}_frequency_source"] = frequency_source
            out[f"c{circuit}_measured_superheat_K"] = measured_superheat
            try:
                pred = fmap.interpolate(te, tc, frequency)
                predictions.append(pred)
                out[f"c{circuit}_frascold_power_kW"] = pred["compressor_power_kW"]
                out[f"c{circuit}_frascold_Q_evap_kW"] = pred["evaporator_capacity_kW"]
                out[f"c{circuit}_frascold_Q_cond_kW"] = pred["condenser_capacity_kW"]
                out[f"c{circuit}_frascold_mass_flow_kg_h"] = pred["mass_flow_kg_h"]
                out[f"c{circuit}_frascold_discharge_temperature_C"] = pred["discharge_temperature_C"]
            except Exception as exc:
                out["model_status"] = "ERROR"
                out["model_error"] += f"C{circuit}: {exc}; "

        if out["model_status"] == "OK" and len(predictions) == active_count and active_count > 0:
            pcomp = sum(p["compressor_power_kW"] for p in predictions)
            qev = sum(p["evaporator_capacity_kW"] for p in predictions)
            qco = sum(p["condenser_capacity_kW"] for p in predictions)
            useful = qco if mode == "heating" else qev
            pmodel = pcomp + fan_power
            out.update({
                "frascold_total_compressor_power_kW": pcomp,
                "frascold_total_Q_evap_kW": qev,
                "frascold_total_Q_cond_kW": qco,
                "frascold_useful_capacity_kW": useful,
                "frascold_plus_fans_power_kW": pmodel,
                "kiona_minus_model_kW": measured-pmodel,
                "model_to_kiona_ratio": pmodel/measured if measured > 0 else np.nan,
                "absolute_error_kW": abs(measured-pmodel),
                "absolute_percentage_error": 100.0*abs(measured-pmodel)/measured if measured > 0 else np.nan,
                "field_referenced_COP_or_EER_proxy": useful/measured if measured > 0 else np.nan,
                "frequency_method_summary": "; ".join(sorted(set(frequency_sources))),
            })
        out["estimated_frequency_Hz_per_active_circuit"] = (
            float(np.mean(active_frequencies))
            if active_frequencies
            else np.nan
        )
        out["mean_active_superheat_K"] = (
            float(np.mean(active_superheats))
            if active_superheats
            else np.nan
        )
        out["superheat_deviation_from_frascold_reference_K"] = (
            out["mean_active_superheat_K"] - 7.0
            if np.isfinite(out["mean_active_superheat_K"])
            else np.nan
        )

        if (
            out["model_status"] == "OK"
            and np.isfinite(measured)
            and np.isfinite(fan_power)
        ):
            target_compressor_power = measured - fan_power
            best_frequency, best_power_residual, diagnostic_status = (
                diagnostic_best_fit_frequency(
                    fmap,
                    circuit_conditions,
                    target_compressor_power,
                )
            )
            out["diagnostic_best_fit_frequency_Hz"] = best_frequency
            out["diagnostic_best_fit_frequency_minus_estimated_Hz"] = (
                best_frequency - out["estimated_frequency_Hz_per_active_circuit"]
                if np.isfinite(best_frequency)
                and np.isfinite(out["estimated_frequency_Hz_per_active_circuit"])
                else np.nan
            )
            out["diagnostic_best_fit_compressor_power_residual_kW"] = (
                best_power_residual
            )
            out["diagnostic_best_fit_frequency_status"] = diagnostic_status
        else:
            out["diagnostic_best_fit_frequency_Hz"] = np.nan
            out["diagnostic_best_fit_frequency_minus_estimated_Hz"] = np.nan
            out["diagnostic_best_fit_compressor_power_residual_kW"] = np.nan
            out["diagnostic_best_fit_frequency_status"] = "unavailable"

        rows.append(out)

    result = pd.DataFrame(rows)
    summaries = []
    for label, g in [("overall", result)] + [(f"HP{int(u)}", gu) for u,gu in result.groupby("unit")]:
        ok = g[g["model_status"] == "OK"].dropna(subset=["frascold_plus_fans_power_kW", "kiona_chiller_unit_electrical_power_kW"])
        row = {"group": label, "stable_periods_total": len(g), "comparison_rows": len(ok)}
        if len(ok):
            x = ok["frascold_plus_fans_power_kW"].to_numpy(float)
            y = ok["kiona_chiller_unit_electrical_power_kW"].to_numpy(float)
            residual = y-x
            row.update({
                "map_coverage_percent": 100.0*len(ok)/len(g) if len(g) else np.nan,
                "MAE_kW": float(np.mean(np.abs(residual))),
                "RMSE_kW": float(np.sqrt(np.mean(residual**2))),
                "MAPE_percent": float(np.mean(np.abs(residual)/y)*100.0),
                "mean_residual_kW": float(np.mean(residual)),
            })
            if len(ok) >= 2 and np.std(x) > 0:
                slope, intercept = np.polyfit(x,y,1)
                yhat = slope*x+intercept
                ssres = np.sum((y-yhat)**2)
                sstot = np.sum((y-np.mean(y))**2)
                row.update({"regression_slope": slope, "regression_intercept_kW": intercept, "R2": 1.0-ssres/sstot if sstot>0 else np.nan, "pearson_r": np.corrcoef(x,y)[0,1]})
        summaries.append(row)

    summary = pd.DataFrame(summaries)
    assumptions = pd.DataFrame([
        ["frequency_method", config.VALIDATION_FREQUENCY_METHOD, "Measured frequency preferred if available; otherwise provisional mapping"],
        ["fan_method", config.VALIDATION_FAN_METHOD, "Normal outdoor-coil fans only"],
        ["fan_rated_unit_kW", config.FAN_RATED_POWER_UNIT_KW, "Four EC fans total"],
        ["external_pump_included", config.VALIDATION_INCLUDE_EXTERNAL_PUMP, "External pumps excluded from validation boundary"],
        ["atmospheric_pressure_bar", config.ATMOSPHERIC_PRESSURE_BAR, "Added to Kiona gauge pressures"],
    ], columns=["parameter", "value", "note"])

    table_io.write_table(result, OUTPUT_VALIDATION_ROWS, export_csv=config.EXPORT_CSV, export_xlsx=config.EXPORT_XLSX, csv_separator=config.CSV_SEPARATOR, csv_decimal=config.CSV_DECIMAL, float_format=config.CSV_FLOAT_FORMAT, sheet_name="ValidationRows")
    table_io.write_table(summary, OUTPUT_VALIDATION_SUMMARY, export_csv=config.EXPORT_CSV, export_xlsx=config.EXPORT_XLSX, csv_separator=config.CSV_SEPARATOR, csv_decimal=config.CSV_DECIMAL, float_format=config.CSV_FLOAT_FORMAT, sheet_name="Summary")
    table_io.write_table(assumptions, OUTPUT_VALIDATION_ASSUMPTIONS, export_csv=config.EXPORT_CSV, export_xlsx=config.EXPORT_XLSX, csv_separator=config.CSV_SEPARATOR, csv_decimal=config.CSV_DECIMAL, float_format=config.CSV_FLOAT_FORMAT, sheet_name="Assumptions")
    pass


if __name__ == "__main__":
    main()
