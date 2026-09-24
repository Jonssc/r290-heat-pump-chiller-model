"""
10_carnot_second_law.py

Carnot and second-law benchmark for the validated R290 stable periods.

Inputs:
- V2 validation_rows
- V2 kiona_stable_periods

Outputs:
- point-by-point Carnot/etaII table
- weighted mode summary

No plots are generated here.

Important boundaries
--------------------
1. Refrigerant-level Carnot:
   measured/inferred R290 saturation Tevap/Tcond.

2. External reservoir Carnot:
   outdoor air and mean water temperature.

3. Compressor etaII:
   Frascold compressor useful capacity / compressor input.

4. Field-referenced unit proxy:
   modeled useful capacity / measured Kiona HERA electrical input.
   This is NOT a directly measured field COP/EER.
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
CARNOT_MODEL_FILE = PROJECT_ROOT / "03_MODELS" / "carnot_model.py"

INPUT_VALIDATION_ROWS = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "validation"
    / "validation_rows.csv"
)

INPUT_STABLE_PERIODS = (
    PROJECT_ROOT
    / "02_PROCESSED_DATA"
    / "kiona_stable_periods.csv"
)

OUTPUT_ROWS = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "carnot"
    / "carnot_second_law_rows"
)

OUTPUT_SUMMARY = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "carnot"
    / "carnot_second_law_summary"
)


# ============================================================
# 3. MODULE LOADING
# ============================================================

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


config = load_module("config_carnot_v2", CONFIG_FILE)
table_io = load_module("table_io_carnot_v2", TABLE_IO_FILE)
carnot = load_module("carnot_model_v2", CARNOT_MODEL_FILE)


# ============================================================
# 4. INPUT HELPERS
# ============================================================

def resolve_table(path):
    if path.exists():
        return path

    csv = path.with_suffix(".csv")

    if csv.exists():
        return csv

    raise FileNotFoundError(path)


def weighted_mean(values, weights):
    values = pd.to_numeric(
        values,
        errors="coerce",
    )

    weights = pd.to_numeric(
        weights,
        errors="coerce",
    )

    valid = (
        values.notna()
        & weights.notna()
        & np.isfinite(values)
        & np.isfinite(weights)
        & (weights > 0)
    )

    if not valid.any():
        return np.nan

    return float(
        np.average(
            values[valid],
            weights=weights[valid],
        )
    )


# ============================================================
# 5. POINT CALCULATION
# ============================================================

def main():
    validation = table_io.read_table(
        resolve_table(
            INPUT_VALIDATION_ROWS
        )
    )

    stable = table_io.read_table(
        resolve_table(
            INPUT_STABLE_PERIODS
        )
    )

    validation["start_time"] = pd.to_datetime(
        validation["start_time"],
        errors="coerce",
    )

    stable_keep = stable[
        [
            column
            for column in [
                "stable_period_id",
                "mean_outdoor_temp_C",
                "mean_hot_side_in_C",
                "mean_hot_side_out_C",
                "nominal_sample_coverage_minutes",
            ]
            if column in stable.columns
        ]
    ].drop_duplicates(
        "stable_period_id"
    )

    data = validation.merge(
        stable_keep,
        on="stable_period_id",
        how="left",
    )

    start = pd.Timestamp(
        config.CARNOT_START_DATE
    )

    end = pd.Timestamp(
        config.CARNOT_END_DATE_EXCLUSIVE
    )

    data = data[
        data["model_status"].astype(str).eq("OK")
        & (data["start_time"] >= start)
        & (data["start_time"] < end)
    ].copy()

    records = []

    for _, row in data.iterrows():
        mode = str(
            row["mode"]
        ).strip().lower()

        useful_total = 0.0
        reversible_ref = 0.0

        active_evap = []
        active_cond = []

        for circuit in (1, 2):
            if not bool(
                row.get(
                    f"c{circuit}_active",
                    False,
                )
            ):
                continue

            Te = pd.to_numeric(
                pd.Series([
                    row.get(
                        f"c{circuit}_T_evap_sat_C",
                        np.nan,
                    )
                ]),
                errors="coerce",
            ).iloc[0]

            Tc = pd.to_numeric(
                pd.Series([
                    row.get(
                        f"c{circuit}_T_cond_sat_C",
                        np.nan,
                    )
                ]),
                errors="coerce",
            ).iloc[0]

            if not np.isfinite(Te) or not np.isfinite(Tc):
                continue

            q_column = (
                f"c{circuit}_frascold_Q_cond_kW"
                if mode == "heating"
                else f"c{circuit}_frascold_Q_evap_kW"
            )

            q = pd.to_numeric(
                pd.Series([
                    row.get(
                        q_column,
                        np.nan,
                    )
                ]),
                errors="coerce",
            ).iloc[0]

            if not np.isfinite(q) or q <= 0:
                continue

            carnot_perf = float(
                carnot.carnot_performance(
                    mode,
                    Te,
                    Tc,
                )
            )

            if not np.isfinite(carnot_perf) or carnot_perf <= 0:
                continue

            useful_total += q
            reversible_ref += (
                q / carnot_perf
            )

            active_evap.append(
                Te
            )

            active_cond.append(
                Tc
            )

        if useful_total <= 0 or reversible_ref <= 0:
            continue

        ref_carnot = (
            useful_total
            / reversible_ref
        )

        compressor_power = pd.to_numeric(
            pd.Series([
                row.get(
                    "frascold_total_compressor_power_kW",
                    np.nan,
                )
            ]),
            errors="coerce",
        ).iloc[0]

        measured_power = pd.to_numeric(
            pd.Series([
                row.get(
                    "kiona_chiller_unit_electrical_power_kW",
                    np.nan,
                )
            ]),
            errors="coerce",
        ).iloc[0]

        compressor_performance = (
            useful_total / compressor_power
            if np.isfinite(compressor_power)
            and compressor_power > 0
            else np.nan
        )

        field_proxy = (
            useful_total / measured_power
            if np.isfinite(measured_power)
            and measured_power > 0
            else np.nan
        )

        water_mean = np.nanmean([
            pd.to_numeric(
                pd.Series([
                    row.get(
                        "mean_hot_side_in_C",
                        np.nan,
                    )
                ]),
                errors="coerce",
            ).iloc[0],
            pd.to_numeric(
                pd.Series([
                    row.get(
                        "mean_hot_side_out_C",
                        np.nan,
                    )
                ]),
                errors="coerce",
            ).iloc[0],
        ])

        outdoor = pd.to_numeric(
            pd.Series([
                row.get(
                    "mean_outdoor_temp_C",
                    np.nan,
                )
            ]),
            errors="coerce",
        ).iloc[0]

        if mode == "heating":
            external_Tevap = outdoor
            external_Tcond = water_mean
        else:
            external_Tevap = water_mean
            external_Tcond = outdoor

        external_carnot = float(
            carnot.carnot_performance(
                mode,
                external_Tevap,
                external_Tcond,
            )
        )

        external_reversible = (
            useful_total / external_carnot
            if np.isfinite(external_carnot)
            and external_carnot > 0
            else np.nan
        )

        record = {
            "stable_period_id": row["stable_period_id"],
            "unit": row["unit"],
            "mode": mode,
            "start_time": row["start_time"],
            "sample_weight_minutes": pd.to_numeric(
                pd.Series([
                    row.get(
                        "nominal_sample_coverage_minutes",
                        np.nan,
                    )
                ]),
                errors="coerce",
            ).iloc[0],
            "active_circuit_count": int(
                bool(row.get("c1_active", False))
                + bool(row.get("c2_active", False))
            ),
            "mean_R290_Tevap_C": np.mean(active_evap),
            "mean_R290_Tcond_C": np.mean(active_cond),
            "mean_R290_lift_K": (
                np.mean(active_cond)
                - np.mean(active_evap)
            ),
            "useful_capacity_model_kW": useful_total,
            "refrigerant_Carnot_COP_or_EER": ref_carnot,
            "Frascold_compressor_COP_or_EER": compressor_performance,
            "field_referenced_unit_proxy_COP_or_EER": field_proxy,
            "refrigerant_reversible_power_kW": reversible_ref,
            "Frascold_compressor_power_kW": compressor_power,
            "Kiona_unit_power_kW": measured_power,
            "etaII_refrigerant_compressor_percent": (
                100.0 * reversible_ref / compressor_power
                if np.isfinite(compressor_power)
                and compressor_power > 0
                else np.nan
            ),
            "etaII_refrigerant_unit_proxy_percent": (
                100.0 * reversible_ref / measured_power
                if np.isfinite(measured_power)
                and measured_power > 0
                else np.nan
            ),
            "external_Carnot_COP_or_EER": external_carnot,
            "external_reversible_power_kW": external_reversible,
            "etaII_external_unit_proxy_percent": (
                100.0 * external_reversible / measured_power
                if np.isfinite(external_reversible)
                and np.isfinite(measured_power)
                and measured_power > 0
                else np.nan
            ),
        }

        records.append(
            record
        )

    result = pd.DataFrame(
        records
    )

    if result.empty:
        raise RuntimeError(
            "No valid Carnot/second-law rows were generated."
        )

    summary_rows = []

    for mode, group in result.groupby("mode"):
        weight = group[
            "sample_weight_minutes"
        ]

        summary_rows.append({
            "mode": mode,
            "stable_periods": len(group),
            "weighted_hours": pd.to_numeric(
                weight,
                errors="coerce",
            ).sum() / 60.0,
            "refrigerant_Carnot_COP_or_EER": weighted_mean(
                group["refrigerant_Carnot_COP_or_EER"],
                weight,
            ),
            "Frascold_compressor_COP_or_EER": weighted_mean(
                group["Frascold_compressor_COP_or_EER"],
                weight,
            ),
            "field_referenced_unit_proxy_COP_or_EER": weighted_mean(
                group["field_referenced_unit_proxy_COP_or_EER"],
                weight,
            ),
            "etaII_refrigerant_compressor_percent": weighted_mean(
                group["etaII_refrigerant_compressor_percent"],
                weight,
            ),
            "etaII_refrigerant_unit_proxy_percent": weighted_mean(
                group["etaII_refrigerant_unit_proxy_percent"],
                weight,
            ),
            "external_Carnot_COP_or_EER": weighted_mean(
                group["external_Carnot_COP_or_EER"],
                weight,
            ),
            "etaII_external_unit_proxy_percent": weighted_mean(
                group["etaII_external_unit_proxy_percent"],
                weight,
            ),
        })

    summary = pd.DataFrame(
        summary_rows
    )

    table_io.write_table(
        result,
        OUTPUT_ROWS,
        export_csv=config.EXPORT_CSV,
        export_xlsx=config.EXPORT_XLSX,
        csv_separator=config.CSV_SEPARATOR,
        csv_decimal=config.CSV_DECIMAL,
        float_format=config.CSV_FLOAT_FORMAT,
        sheet_name="CarnotRows",
    )

    table_io.write_table(
        summary,
        OUTPUT_SUMMARY,
        export_csv=config.EXPORT_CSV,
        export_xlsx=config.EXPORT_XLSX,
        csv_separator=config.CSV_SEPARATOR,
        csv_decimal=config.CSV_DECIMAL,
        float_format=config.CSV_FLOAT_FORMAT,
        sheet_name="Summary",
    )

    pass


if __name__ == "__main__":
    main()
