"""
11_standardized_SCOP_SEER.py

Standardized active-mode seasonal performance screening for the R290 HERA.

Reported:
- fixed standard anchor-point COP/EER;
- refrigerant-level Carnot performance and etaII at anchors;
- modeled SCOPon,50 and SEERon,7;
- one-HERA and three-HERA active-mode screening.

This is NOT a certified full product SCOP/SEER calculation because off-mode,
standby, thermostat-off and crankcase-heater consumption are not available.

No plots are generated here.
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

FRASCOLD_GRID_MODEL_FILE = (
    PROJECT_ROOT
    / "03_MODELS"
    / "frascold_grid_model.py"
)

HERA_MODEL_FILE = (
    PROJECT_ROOT
    / "03_MODELS"
    / "hera_model.py"
)

MODEL_FACTORY_FILE = (
    PROJECT_ROOT
    / "03_MODELS"
    / "model_factory.py"
)

PLANT_MODEL_FILE = (
    PROJECT_ROOT
    / "03_MODELS"
    / "plant_model.py"
)

CARNOT_MODEL_FILE = (
    PROJECT_ROOT
    / "03_MODELS"
    / "carnot_model.py"
)

SEASONAL_MODEL_FILE = (
    PROJECT_ROOT
    / "03_MODELS"
    / "seasonal_performance_model.py"
)

INPUT_FRASCOLD_DATABASE = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "databases"
    / "frascold_performance_grid.csv"
)

INPUT_HX_CALIBRATION = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "databases"
    / "hera_hx_calibration.csv"
)

OUTPUT_ANCHORS = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "carnot"
    / "standardized_anchor_points"
)

OUTPUT_BINS = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "carnot"
    / "standardized_seasonal_bins"
)

OUTPUT_SUMMARY = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "carnot"
    / "standardized_SCOP_SEER_summary"
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


config = load_module("config_standard_seasonal", CONFIG_FILE)
table_io = load_module("table_io_standard_seasonal", TABLE_IO_FILE)
grid_module = load_module("grid_standard_seasonal", FRASCOLD_GRID_MODEL_FILE)
hera_module = load_module("hera_standard_seasonal", HERA_MODEL_FILE)
factory = load_module("factory_standard_seasonal", MODEL_FACTORY_FILE)
plant = load_module("plant_standard_seasonal", PLANT_MODEL_FILE)
carnot = load_module("carnot_standard_seasonal", CARNOT_MODEL_FILE)
seasonal = load_module("seasonal_standard_seasonal", SEASONAL_MODEL_FILE)


# ============================================================
# 4. MODEL
# ============================================================

def build_model():
    return factory.build_circuit_model(
        frascold_database=INPUT_FRASCOLD_DATABASE,
        calibration_file=INPUT_HX_CALIBRATION,
        config=config,
        table_io=table_io,
        frascold_grid_module=grid_module,
        hera_module=hera_module,
    )


def best_one_hera(
    model,
    mode,
    load_kW,
    outdoor_C,
    water_out_C,
):
    return plant.best_unit_operation(
        model,
        mode,
        float(load_kW),
        float(outdoor_C),
        float(water_out_C),
        config.DISPATCH_FAN_CANDIDATES,
        include_unit_pump=False,
        frequency_seed_Hz=config.ANALYTIC_REFERENCE_FREQUENCY_HZ,
    )


def one_hera_minimum_state(
    model,
    calibrations,
    mode,
    outdoor_C,
    water_out_C,
):
    fan = calibrations[mode].reference_fan_speed_fraction

    result = model.safe_evaluate(
        hera_module.CircuitCase(
            mode=mode,
            outdoor_C=float(outdoor_C),
            water_out_C=float(water_out_C),
            frequency_Hz=config.FREQUENCY_MIN_HZ,
            fan_speed_fraction=float(fan),
        )
    )

    if result.get("model_status") != "OK":
        return None

    return {
        "capacity_kW": float(result["Quseful_kW"]),
        "power_kW": float(result["Pcircuit_comp_plus_fan_kW"]),
        "frequency_Hz": float(result["frequency_Hz"]),
        "fan_speed_fraction": float(result["fan_speed_fraction"]),
        "active_circuits": 1,
        "T_evap_C": float(result["T_evap_C"]),
        "T_cond_C": float(result["T_cond_C"]),
    }


# ============================================================
# 5. HEATING DESIGN LOAD
# ============================================================

def determine_heating_design_capacity(
    model,
):
    # At the conservative TOL (-7 °C), use the maximum two-circuit HERA output.
    max_state = plant.best_unit_operation_fixed_circuits(
        model,
        "heating",
        unit_load_kW=1.0,
        outdoor_C=config.STANDARD_HEATING_TOL_C,
        water_out_C=config.STANDARD_HEATING_WATER_OUT_C,
        active_circuits=2,
        fan_candidates=[1.0],
        frequency_seed_Hz=config.FREQUENCY_MAX_HZ,
    )

    # The helper above solves to a supplied load, so calculate direct 70-Hz
    # capacity instead.
    from copy import deepcopy

    # Find a direct valid two-circuit 70-Hz reference using the HERA model.
    circuit = model.safe_evaluate(
        hera_module.CircuitCase(
            mode="heating",
            outdoor_C=config.STANDARD_HEATING_TOL_C,
            water_out_C=config.STANDARD_HEATING_WATER_OUT_C,
            frequency_Hz=config.FREQUENCY_MAX_HZ,
            fan_speed_fraction=1.0,
        )
    )

    if circuit.get("model_status") != "OK":
        raise RuntimeError(
            "Could not determine heating capacity at TOL."
        )

    capacity_at_TOL = 2.0 * float(circuit["Quseful_kW"])

    # Standard heating load relation:
    # Ph(TOL) = Pdesign * (TOL-16)/(Tdesign-16)
    fraction_at_TOL = float(
        seasonal.heating_part_load_fraction(
            config.STANDARD_HEATING_TOL_C,
            config.STANDARD_HEATING_TDESIGN_C,
        )
    )

    if fraction_at_TOL <= 0:
        raise RuntimeError(
            "Invalid heating part-load fraction at TOL."
        )

    return capacity_at_TOL / fraction_at_TOL


# ============================================================
# 6. COOLING DESIGN LOAD
# ============================================================

def determine_cooling_design_capacity(
    model,
):
    circuit = model.safe_evaluate(
        hera_module.CircuitCase(
            mode="cooling",
            outdoor_C=config.STANDARD_COOLING_TDESIGN_C,
            water_out_C=config.STANDARD_COOLING_WATER_OUT_C,
            frequency_Hz=config.FREQUENCY_MAX_HZ,
            fan_speed_fraction=(
                config.HERA_FALLBACK_CALIBRATION[
                    "cooling"
                ]["reference_fan_speed_fraction"]
            ),
        )
    )

    if circuit.get("model_status") != "OK":
        raise RuntimeError(
            "Could not determine cooling design capacity."
        )

    return 2.0 * float(
        circuit["Quseful_kW"]
    )


# ============================================================
# 7. ONE-HERA BIN CALCULATION
# ============================================================

def one_hera_bin(
    model,
    calibrations,
    mode,
    outdoor_C,
    required_load_kW,
):
    water_out_C = (
        config.STANDARD_HEATING_WATER_OUT_C
        if mode == "heating"
        else config.STANDARD_COOLING_WATER_OUT_C
    )

    minimum = one_hera_minimum_state(
        model,
        calibrations,
        mode,
        outdoor_C,
        water_out_C,
    )

    if minimum is None:
        return None

    qmin = minimum["capacity_kW"]
    pmin = minimum["power_kW"]

    if required_load_kW < qmin:
        average_power = float(
            seasonal.cycling_average_power_kW(
                required_load_kW,
                qmin,
                pmin,
                config.STANDARD_CYCLING_DEGRADATION_COEFFICIENT,
            )
        )

        return {
            "mode": mode,
            "outdoor_C": outdoor_C,
            "required_load_kW": required_load_kW,
            "delivered_load_kW": required_load_kW,
            "electrical_power_kW": average_power,
            "COP_or_EER": (
                required_load_kW / average_power
                if average_power > 0
                else np.nan
            ),
            "active_circuits": 1,
            "frequency_Hz": config.FREQUENCY_MIN_HZ,
            "cycling_below_minimum_capacity": True,
            "supplementary_heat_kW": 0.0,
            "T_evap_C": minimum["T_evap_C"],
            "T_cond_C": minimum["T_cond_C"],
        }

    operation = best_one_hera(
        model,
        mode,
        required_load_kW,
        outdoor_C,
        water_out_C,
    )

    if operation is not None:
        return {
            **operation,
            # best_unit_operation() does not carry the ambient condition in
            # its return dictionary.  Preserve it explicitly because the
            # standardized anchor plots compare the four SCOP/SEER outdoor
            # temperatures directly against their matching Carnot values.
            "mode": mode,
            "outdoor_C": outdoor_C,
            "required_load_kW": required_load_kW,
            "delivered_load_kW": required_load_kW,
            "electrical_power_kW": operation["unit_total_power_kW"],
            "COP_or_EER": operation["unit_COP_or_EER"],
            "cycling_below_minimum_capacity": False,
            "supplementary_heat_kW": 0.0,
        }

    # Outside HERA capacity in heating: electrical-resistance backup is used.
    if mode == "heating":
        direct = model.safe_evaluate(
            hera_module.CircuitCase(
                mode="heating",
                outdoor_C=outdoor_C,
                water_out_C=water_out_C,
                frequency_Hz=config.FREQUENCY_MAX_HZ,
                fan_speed_fraction=1.0,
            )
        )

        if direct.get("model_status") != "OK":
            return None

        max_capacity = 2.0 * float(
            direct["Quseful_kW"]
        )

        max_power = 2.0 * float(
            direct["Pcircuit_comp_plus_fan_kW"]
        )

        supplementary = max(
            required_load_kW
            - max_capacity,
            0.0,
        )

        total_power = (
            max_power
            + supplementary
        )

        return {
            "mode": mode,
            "outdoor_C": outdoor_C,
            "required_load_kW": required_load_kW,
            "delivered_load_kW": required_load_kW,
            "electrical_power_kW": total_power,
            "COP_or_EER": (
                required_load_kW / total_power
                if total_power > 0
                else np.nan
            ),
            "active_circuits": 2,
            "frequency_Hz": config.FREQUENCY_MAX_HZ,
            "cycling_below_minimum_capacity": False,
            "supplementary_heat_kW": supplementary,
            "T_evap_C": direct["T_evap_C"],
            "T_cond_C": direct["T_cond_C"],
        }

    return None


# ============================================================
# 8. THREE-HERA BIN CALCULATION
# ============================================================

def three_hera_bin(
    model,
    calibrations,
    mode,
    outdoor_C,
    required_load_kW,
):
    if required_load_kW <= 0:
        return {
            "mode": mode,
            "outdoor_C": outdoor_C,
            "required_load_kW": 0.0,
            "delivered_load_kW": 0.0,
            "electrical_power_kW": 0.0,
            "COP_or_EER": np.nan,
            "active_units": 0,
            "supplementary_heat_kW": 0.0,
        }

    best = None

    for active_units in (1, 2, 3):
        unit_load = (
            required_load_kW
            / active_units
        )

        unit_result = one_hera_bin(
            model,
            calibrations,
            mode,
            outdoor_C,
            unit_load,
        )

        if unit_result is None:
            continue

        # For plant staging comparison, do not allow per-unit supplementary
        # heating until all 3 units are active.
        supplementary_per_unit = float(
            unit_result.get(
                "supplementary_heat_kW",
                0.0,
            )
        )

        if supplementary_per_unit > 0 and active_units < 3:
            continue

        total_power = (
            active_units
            * float(
                unit_result["electrical_power_kW"]
            )
        )

        candidate = {
            "mode": mode,
            "outdoor_C": outdoor_C,
            "required_load_kW": required_load_kW,
            "delivered_load_kW": required_load_kW,
            "electrical_power_kW": total_power,
            "COP_or_EER": (
                required_load_kW
                / total_power
                if total_power > 0
                else np.nan
            ),
            "active_units": active_units,
            "active_circuits_per_unit": unit_result.get(
                "active_circuits",
                np.nan,
            ),
            "frequency_Hz": unit_result.get(
                "frequency_Hz",
                np.nan,
            ),
            "cycling_below_minimum_capacity": unit_result.get(
                "cycling_below_minimum_capacity",
                False,
            ),
            "supplementary_heat_kW": (
                active_units
                * supplementary_per_unit
            ),
            "T_evap_C": unit_result.get(
                "T_evap_C",
                np.nan,
            ),
            "T_cond_C": unit_result.get(
                "T_cond_C",
                np.nan,
            ),
        }

        if (
            best is None
            or candidate["electrical_power_kW"]
            < best["electrical_power_kW"]
        ):
            best = candidate

    return best


# ============================================================
# 9. STANDARD BINS
# ============================================================

def build_bins(
    model,
    calibrations,
    mode,
    design_load_one_HERA_kW,
):
    if mode == "heating":
        bin_hours = config.STANDARD_HEATING_BIN_HOURS
        load_fraction = lambda T: seasonal.heating_part_load_fraction(
            T,
            config.STANDARD_HEATING_TDESIGN_C,
        )
    else:
        bin_hours = config.STANDARD_COOLING_BIN_HOURS
        load_fraction = lambda T: seasonal.cooling_part_load_fraction(
            T,
            config.STANDARD_COOLING_TDESIGN_C,
        )

    rows = []

    for outdoor_C, hours in bin_hours.items():
        fraction = float(
            load_fraction(
                outdoor_C
            )
        )

        load_one = (
            design_load_one_HERA_kW
            * fraction
        )

        one = one_hera_bin(
            model,
            calibrations,
            mode,
            float(outdoor_C),
            load_one,
        )

        load_three = (
            3.0
            * design_load_one_HERA_kW
            * fraction
        )

        three = three_hera_bin(
            model,
            calibrations,
            mode,
            float(outdoor_C),
            load_three,
        )

        for scope, result, load in (
            ("one_HERA", one, load_one),
            ("three_HERA_plant", three, load_three),
        ):
            if result is None:
                rows.append({
                    "mode": mode,
                    "scope": scope,
                    "outdoor_C": float(outdoor_C),
                    "bin_hours": float(hours),
                    "part_load_fraction": fraction,
                    "required_load_kW": load,
                    "model_status": "INVALID",
                })
                continue

            row = {
                **result,
                "scope": scope,
                "bin_hours": float(hours),
                "part_load_fraction": fraction,
                "model_status": "OK",
            }

            row["useful_energy_kWh"] = (
                float(
                    result["delivered_load_kW"]
                )
                * float(hours)
            )

            row["electrical_energy_kWh"] = (
                float(
                    result["electrical_power_kW"]
                )
                * float(hours)
            )

            row["supplementary_heat_energy_kWh"] = (
                float(
                    result.get(
                        "supplementary_heat_kW",
                        0.0,
                    )
                )
                * float(hours)
            )

            rows.append(
                row
            )

    return pd.DataFrame(
        rows
    )


# ============================================================
# 10. ANCHOR POINTS
# ============================================================

def build_anchor_points(
    model,
    calibrations,
    heating_design,
    cooling_design,
):
    rows = []

    for mode, temperatures, design in (
        (
            "heating",
            config.STANDARD_HEATING_ANCHOR_OUTDOOR_C,
            heating_design,
        ),
        (
            "cooling",
            config.STANDARD_COOLING_ANCHOR_OUTDOOR_C,
            cooling_design,
        ),
    ):
        for outdoor_C in temperatures:
            if mode == "heating":
                fraction = float(
                    seasonal.heating_part_load_fraction(
                        outdoor_C,
                        config.STANDARD_HEATING_TDESIGN_C,
                    )
                )
            else:
                fraction = float(
                    seasonal.cooling_part_load_fraction(
                        outdoor_C,
                        config.STANDARD_COOLING_TDESIGN_C,
                    )
                )

            load = design * fraction

            result = one_hera_bin(
                model,
                calibrations,
                mode,
                float(outdoor_C),
                float(load),
            )

            if result is None:
                continue

            Te = result.get(
                "T_evap_C",
                np.nan,
            )

            Tc = result.get(
                "T_cond_C",
                np.nan,
            )

            carnot_perf = float(
                carnot.carnot_performance(
                    mode,
                    Te,
                    Tc,
                )
            )

            eta = (
                100.0
                * result["COP_or_EER"]
                / carnot_perf
                if np.isfinite(carnot_perf)
                and carnot_perf > 0
                else np.nan
            )

            rows.append({
                **result,
                "standard_anchor": True,
                "part_load_fraction": fraction,
                "Carnot_COP_or_EER": carnot_perf,
                "etaII_unit_percent": eta,
            })

    return pd.DataFrame(
        rows
    )


# ============================================================
# 11. MAIN
# ============================================================

def main():
    model, calibrations = build_model()

    heating_design = determine_heating_design_capacity(
        model
    )

    cooling_design = determine_cooling_design_capacity(
        model
    )

    heating_bins = build_bins(
        model,
        calibrations,
        "heating",
        heating_design,
    )

    cooling_bins = build_bins(
        model,
        calibrations,
        "cooling",
        cooling_design,
    )

    bins = pd.concat(
        [
            heating_bins,
            cooling_bins,
        ],
        ignore_index=True,
    )

    anchors = build_anchor_points(
        model,
        calibrations,
        heating_design,
        cooling_design,
    )

    summary_rows = []

    for (mode, scope), group in bins.groupby(
        [
            "mode",
            "scope",
        ]
    ):
        valid = group[
            group["model_status"].astype(str).eq("OK")
        ]

        useful = pd.to_numeric(
            valid["useful_energy_kWh"],
            errors="coerce",
        ).sum()

        electrical = pd.to_numeric(
            valid["electrical_energy_kWh"],
            errors="coerce",
        ).sum()

        supplementary = pd.to_numeric(
            valid[
                "supplementary_heat_energy_kWh"
            ],
            errors="coerce",
        ).sum()

        summary_rows.append({
            "mode": mode,
            "scope": scope,
            "heating_water_out_C": (
                config.STANDARD_HEATING_WATER_OUT_C
                if mode == "heating"
                else np.nan
            ),
            "cooling_water_out_C": (
                config.STANDARD_COOLING_WATER_OUT_C
                if mode == "cooling"
                else np.nan
            ),
            "design_load_kW": (
                heating_design
                if mode == "heating"
                else cooling_design
            ) * (
                3.0
                if scope == "three_HERA_plant"
                else 1.0
            ),
            "active_mode_seasonal_index": seasonal.seasonal_index(
                useful,
                electrical,
            ),
            "seasonal_index_name": (
                "SCOPon,50"
                if mode == "heating"
                else "SEERon,7"
            ),
            "useful_energy_kWh": useful,
            "electrical_energy_kWh": electrical,
            "supplementary_heat_energy_kWh": supplementary,
            "cycling_degradation_coefficient": (
                config.STANDARD_CYCLING_DEGRADATION_COEFFICIENT
            ),
            "full_certified_SCOP_SEER": False,
            "external_water_pumps_included": False,
        })

    summary = pd.DataFrame(
        summary_rows
    )

    table_io.write_table(
        anchors,
        OUTPUT_ANCHORS,
        export_csv=config.EXPORT_CSV,
        export_xlsx=config.EXPORT_XLSX,
        csv_separator=config.CSV_SEPARATOR,
        csv_decimal=config.CSV_DECIMAL,
        float_format=config.CSV_FLOAT_FORMAT,
        sheet_name="Anchors",
    )

    table_io.write_table(
        bins,
        OUTPUT_BINS,
        export_csv=config.EXPORT_CSV,
        export_xlsx=config.EXPORT_XLSX,
        csv_separator=config.CSV_SEPARATOR,
        csv_decimal=config.CSV_DECIMAL,
        float_format=config.CSV_FLOAT_FORMAT,
        sheet_name="Bins",
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
