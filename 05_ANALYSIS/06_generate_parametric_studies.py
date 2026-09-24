"""
06_generate_parametric_studies.py

Creates reusable analytical study TABLES only.
No figures are created here.

The plotting script reads these tables later. This keeps model calculation and
visualization independent.

All source/result file paths are collected in Section 2.
All studies can be enabled/disabled in Section 3.
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
#    CHANGE HERE IF A DIFFERENT FILE IS USED
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONFIG_FILE = PROJECT_ROOT / "00_CONFIG" / "config.py"
TABLE_IO_FILE = PROJECT_ROOT / "00_CONFIG" / "table_io.py"

FRASCOLD_GRID_MODEL_FILE = PROJECT_ROOT / "03_MODELS" / "frascold_grid_model.py"
HERA_MODEL_FILE = PROJECT_ROOT / "03_MODELS" / "hera_model.py"
MODEL_FACTORY_FILE = PROJECT_ROOT / "03_MODELS" / "model_factory.py"
PLANT_MODEL_FILE = PROJECT_ROOT / "03_MODELS" / "plant_model.py"
GLYCOL_MODEL_FILE = PROJECT_ROOT / "03_MODELS" / "glycol_model.py"
INPUT_GLYCOL_WORKBOOK = (
    PROJECT_ROOT / "01_RAW_DATA" / "Glycol" / "DOWCAL200E_Property_Tables_20-50vol.xlsx"
)

INPUT_FRASCOLD_DATABASE = (
    PROJECT_ROOT / "06_RESULTS" / "databases" / "frascold_performance_grid.csv"
)

INPUT_HX_CALIBRATION = (
    PROJECT_ROOT / "06_RESULTS" / "databases" / "hera_hx_calibration.csv"
)

OUTPUT_FOLDER = (
    PROJECT_ROOT / "06_RESULTS" / "optimization" / "parametric"
)


# ============================================================
# 3. STUDY SELECTION
# ============================================================

RUN_HEATING_WATER_TEMPERATURE = True
RUN_COOLING_WATER_TEMPERATURE = True
RUN_OUTDOOR_TEMPERATURE = True
RUN_DIRECT_FREQUENCY = True

RUN_AIR_UA = True
RUN_WATER_UA = True
RUN_FOULING = True
RUN_FAN = True
RUN_WATER_FLOW_AND_PUMP = True
RUN_GLYCOL_PERFORMANCE = True

RUN_AIR_UA_X_FAN = True
RUN_WATER_UA_X_FLOW = True
RUN_AIR_UA_X_WATER_UA = True



# ============================================================
# 4. MODULE LOADING
# ============================================================

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


config = load_module("config_parametric_v2", CONFIG_FILE)
table_io = load_module("table_io_parametric_v2", TABLE_IO_FILE)
grid_module = load_module("frascold_grid_parametric_v2", FRASCOLD_GRID_MODEL_FILE)
hera_module = load_module("hera_parametric_v2", HERA_MODEL_FILE)
factory = load_module("factory_parametric_v2", MODEL_FACTORY_FILE)
plant = load_module("plant_parametric_v2", PLANT_MODEL_FILE)
glycol_model = load_module("glycol_parametric_v2", GLYCOL_MODEL_FILE)


# ============================================================
# 5. OUTPUT HELPER
# ============================================================

def export_table(dataframe, name, sheet):
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
# 6. MODEL / BASELINE
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


def mode_baseline(mode, calibrations):
    if mode == "heating":
        return {
            "outdoor_C": config.ANALYTIC_HEATING_OUTDOOR_C,
            "water_out_C": config.HEATING_WATER_OUT_C,
            "frequency_Hz": config.ANALYTIC_REFERENCE_FREQUENCY_HZ,
            "fan_speed_fraction": calibrations[mode].reference_fan_speed_fraction,
        }

    return {
        "outdoor_C": config.ANALYTIC_COOLING_OUTDOOR_C,
        "water_out_C": config.COOLING_WATER_OUT_C,
        "frequency_Hz": config.ANALYTIC_REFERENCE_FREQUENCY_HZ,
        "fan_speed_fraction": calibrations[mode].reference_fan_speed_fraction,
    }


def baseline_target(model, calibrations, mode):
    b = mode_baseline(mode, calibrations)

    result = model.safe_evaluate(
        hera_module.CircuitCase(
            mode=mode,
            outdoor_C=b["outdoor_C"],
            water_out_C=b["water_out_C"],
            frequency_Hz=b["frequency_Hz"],
            fan_speed_fraction=b["fan_speed_fraction"],
        )
    )

    if result.get("model_status") != "OK":
        raise RuntimeError(
            f"Could not create {mode} reference target: {result.get('model_error')}"
        )

    return float(result["Quseful_kW"])


def fixed_load_result(
    model,
    calibrations,
    mode,
    target_Q_kW,
    **changed,
):
    b = mode_baseline(mode, calibrations)

    case = hera_module.CircuitCase(
        mode=mode,
        outdoor_C=float(changed.get("outdoor_C", b["outdoor_C"])),
        water_out_C=float(changed.get("water_out_C", b["water_out_C"])),
        frequency_Hz=float(b["frequency_Hz"]),
        fan_speed_fraction=float(
            changed.get("fan_speed_fraction", b["fan_speed_fraction"])
        ),
        air_UA_multiplier=float(changed.get("air_UA_multiplier", 1.0)),
        water_UA_multiplier=float(changed.get("water_UA_multiplier", 1.0)),
        water_flow_fraction=float(changed.get("water_flow_fraction", 1.0)),
        glycol_water_UA_factor=float(changed.get("glycol_water_UA_factor", 1.0)),
    )

    result = model.solve_frequency_for_load(
        case,
        target_Q_kW,
    )

    result["mode"] = mode
    result["reference_target_Q_kW"] = float(target_Q_kW)
    return result


# ============================================================
# 7. 1D STUDIES
# ============================================================

def create_1d_studies(model, calibrations, targets):
    # Heating water temperature.
    if RUN_HEATING_WATER_TEMPERATURE:
        rows = [
            fixed_load_result(
                model,
                calibrations,
                "heating",
                targets["heating"],
                water_out_C=value,
            )
            for value in config.HEATING_WATER_TEMP_STUDY_C
        ]
        export_table(
            pd.DataFrame(rows),
            "01_heating_water_temperature_fixed_load",
            "HeatingWater",
        )

    # Cooling water temperature.
    if RUN_COOLING_WATER_TEMPERATURE:
        rows = [
            fixed_load_result(
                model,
                calibrations,
                "cooling",
                targets["cooling"],
                water_out_C=value,
            )
            for value in config.COOLING_WATER_TEMP_STUDY_C
        ]
        export_table(
            pd.DataFrame(rows),
            "02_cooling_water_temperature_fixed_load",
            "CoolingWater",
        )

    # Outdoor temperature.
    if RUN_OUTDOOR_TEMPERATURE:
        rows = []

        for value in config.HEATING_OUTDOOR_TEMP_STUDY_C:
            rows.append(
                fixed_load_result(
                    model,
                    calibrations,
                    "heating",
                    targets["heating"],
                    outdoor_C=value,
                )
            )

        for value in config.COOLING_OUTDOOR_TEMP_STUDY_C:
            rows.append(
                fixed_load_result(
                    model,
                    calibrations,
                    "cooling",
                    targets["cooling"],
                    outdoor_C=value,
                )
            )

        export_table(
            pd.DataFrame(rows),
            "03_outdoor_temperature_fixed_load",
            "OutdoorTemperature",
        )

    # Direct compressor-frequency map under fixed external boundary conditions.
    if RUN_DIRECT_FREQUENCY:
        rows = []

        for mode in ("heating", "cooling"):
            b = mode_baseline(mode, calibrations)

            for frequency in np.arange(
                config.FREQUENCY_MIN_HZ,
                config.FREQUENCY_MAX_HZ
                + 0.5 * config.FREQUENCY_STEP_HZ,
                config.FREQUENCY_STEP_HZ,
            ):
                row = model.safe_evaluate(
                    hera_module.CircuitCase(
                        mode=mode,
                        outdoor_C=b["outdoor_C"],
                        water_out_C=b["water_out_C"],
                        frequency_Hz=float(frequency),
                        fan_speed_fraction=b["fan_speed_fraction"],
                    )
                )
                rows.append(row)

        export_table(
            pd.DataFrame(rows),
            "04_direct_compressor_frequency",
            "Frequency",
        )

    # Air-side effective UA.
    if RUN_AIR_UA:
        rows = []

        for mode in ("heating", "cooling"):
            for value in config.AIR_UA_FINE_MULTIPLIERS:
                rows.append(
                    fixed_load_result(
                        model,
                        calibrations,
                        mode,
                        targets[mode],
                        air_UA_multiplier=value,
                    )
                )

        export_table(
            pd.DataFrame(rows),
            "05_air_UA_fixed_load",
            "AirUA",
        )

    # Water-side effective UA.
    if RUN_WATER_UA:
        rows = []

        for mode in ("heating", "cooling"):
            for value in config.WATER_UA_FINE_MULTIPLIERS:
                rows.append(
                    fixed_load_result(
                        model,
                        calibrations,
                        mode,
                        targets[mode],
                        water_UA_multiplier=value,
                    )
                )

        export_table(
            pd.DataFrame(rows),
            "06_water_UA_fixed_load",
            "WaterUA",
        )

    # Fouling: separate air-side and water-side UA reduction.
    if RUN_FOULING:
        rows = []

        for mode in ("heating", "cooling"):
            for multiplier in config.FOULING_UA_MULTIPLIERS:
                air = fixed_load_result(
                    model,
                    calibrations,
                    mode,
                    targets[mode],
                    air_UA_multiplier=multiplier,
                )
                air["fouling_location"] = "air_side"
                air["UA_remaining_fraction"] = multiplier
                rows.append(air)

                water = fixed_load_result(
                    model,
                    calibrations,
                    mode,
                    targets[mode],
                    water_UA_multiplier=multiplier,
                )
                water["fouling_location"] = "water_side"
                water["UA_remaining_fraction"] = multiplier
                rows.append(water)

        export_table(
            pd.DataFrame(rows),
            "07_fouling_fixed_load",
            "Fouling",
        )

    # Fan sensitivity.
    if RUN_FAN:
        rows = []

        for mode in ("heating", "cooling"):
            for fan in config.FAN_FINE_FRACTIONS:
                rows.append(
                    fixed_load_result(
                        model,
                        calibrations,
                        mode,
                        targets[mode],
                        fan_speed_fraction=fan,
                    )
                )

        export_table(
            pd.DataFrame(rows),
            "08_fan_speed_fixed_load",
            "Fan",
        )

    # Water flow + nameplate pump screening.
    if RUN_WATER_FLOW_AND_PUMP:
        rows = []

        for mode in ("heating", "cooling"):
            for flow in config.WATER_FLOW_FINE_FRACTIONS:
                row = fixed_load_result(
                    model,
                    calibrations,
                    mode,
                    targets[mode],
                    water_flow_fraction=flow,
                )

                pump_power = plant.unit_pump_power_kW(
                    speed_fraction=flow,
                    electrical_reference_kW=config.UNIT_PUMP_ELECTRICAL_REFERENCE_KW,
                    motor_load_factor=config.PUMP_MOTOR_LOAD_FACTOR,
                    power_exponent=config.PUMP_POWER_EXPONENT,
                )

                row["screening_unit_pump_power_kW"] = pump_power

                if bool(row.get("feasible", False)):
                    circuit_power = float(
                        row["Pcircuit_comp_plus_fan_kW"]
                    )
                    row["COP_or_EER_with_unit_pump_screening"] = (
                        targets[mode]
                        / (
                            circuit_power
                            + pump_power
                        )
                    )
                else:
                    row["COP_or_EER_with_unit_pump_screening"] = np.nan

                rows.append(row)

        export_table(
            pd.DataFrame(rows),
            "09_water_flow_and_pump_fixed_load",
            "WaterFlowPump",
        )


    # Glycol concentration screening based on the complete 20...50 vol-% property
    # workbook. 29 vol-% is intentionally NOT used here: it belongs only to the
    # separate OE/Belimo meter-setting validation.
    if RUN_GLYCOL_PERFORMANCE:
        if not INPUT_GLYCOL_WORKBOOK.exists():
            raise FileNotFoundError(
                f"Glycol property workbook not found:\n{INPUT_GLYCOL_WORKBOOK}"
            )

        glycol_tables = glycol_model.load_property_workbook(
            INPUT_GLYCOL_WORKBOOK
        )

        rows = []

        for mode in ("heating", "cooling"):
            b = mode_baseline(
                mode,
                calibrations,
            )

            # Use leaving-fluid temperature as the representative liquid
            # temperature for this screening, matching the previous analytic model.
            liquid_temperature_C = float(
                b["water_out_C"]
            )

            for concentration in config.GLYCOL_CONCENTRATIONS_VOL_PERCENT:
                # Water (0%) remains in the property plots. The current IF97
                # helper does not yet expose mu/k, so the Dittus-Boelter /
                # pressure-drop performance screening uses only complete glycol
                # property cases.
                if concentration == 0:
                    continue

                factors = glycol_model.relative_glycol_factors(
                    glycol_tables,
                    int(concentration),
                    liquid_temperature_C,
                    mode,
                    reference_concentration_percent=(
                        config.GLYCOL_REFERENCE_CONCENTRATION_PERCENT
                    ),
                    water_side_resistance_fraction=(
                        config.WATER_SIDE_RESISTANCE_FRACTION
                    ),
                )

                if factors is None:
                    continue

                row = fixed_load_result(
                    model,
                    calibrations,
                    mode,
                    targets[mode],
                    glycol_water_UA_factor=(
                        factors[
                            "relative_effective_water_HX_UA"
                        ]
                    ),
                )

                row.update(
                    factors
                )

                pump_power = (
                    config.UNIT_PUMP_ELECTRICAL_REFERENCE_KW
                    * config.PUMP_MOTOR_LOAD_FACTOR
                    * factors[
                        "relative_pump_power_same_Q_dT"
                    ]
                )

                row[
                    "screening_unit_pump_power_kW"
                ] = pump_power

                if bool(
                    row.get(
                        "feasible",
                        False,
                    )
                ):
                    row[
                        "COP_or_EER_with_unit_pump_screening"
                    ] = (
                        targets[mode]
                        / (
                            float(
                                row[
                                    "Pcircuit_comp_plus_fan_kW"
                                ]
                            )
                            + pump_power
                        )
                    )
                else:
                    row[
                        "COP_or_EER_with_unit_pump_screening"
                    ] = np.nan

                rows.append(
                    row
                )

        export_table(
            pd.DataFrame(
                rows
            ),
            "10b_glycol_property_based_performance",
            "GlycolPerformance",
        )



# ============================================================
# 8. 2D STUDIES
# ============================================================

def create_2d_studies(model, calibrations, targets):
    # Air UA x fan speed.
    if RUN_AIR_UA_X_FAN:
        for mode in ("heating", "cooling"):
            rows = []

            for air_ua in config.AIR_UA_FINE_MULTIPLIERS:
                for fan in config.FAN_FINE_FRACTIONS:
                    row = fixed_load_result(
                        model,
                        calibrations,
                        mode,
                        targets[mode],
                        air_UA_multiplier=air_ua,
                        fan_speed_fraction=fan,
                    )
                    rows.append(row)

            export_table(
                pd.DataFrame(rows),
                f"11_{mode}_air_UA_x_fan_fixed_load",
                "AirUAFan",
            )

    # Water UA x water flow/pump.
    if RUN_WATER_UA_X_FLOW:
        for mode in ("heating", "cooling"):
            rows = []

            for water_ua in config.WATER_UA_FINE_MULTIPLIERS:
                for flow in config.WATER_FLOW_FINE_FRACTIONS:
                    row = fixed_load_result(
                        model,
                        calibrations,
                        mode,
                        targets[mode],
                        water_UA_multiplier=water_ua,
                        water_flow_fraction=flow,
                    )

                    pump_power = plant.unit_pump_power_kW(
                        speed_fraction=flow,
                        electrical_reference_kW=config.UNIT_PUMP_ELECTRICAL_REFERENCE_KW,
                        motor_load_factor=config.PUMP_MOTOR_LOAD_FACTOR,
                        power_exponent=config.PUMP_POWER_EXPONENT,
                    )

                    row["screening_unit_pump_power_kW"] = pump_power

                    if bool(row.get("feasible", False)):
                        row["COP_or_EER_with_unit_pump_screening"] = (
                            targets[mode]
                            / (
                                float(row["Pcircuit_comp_plus_fan_kW"])
                                + pump_power
                            )
                        )
                    else:
                        row["COP_or_EER_with_unit_pump_screening"] = np.nan

                    rows.append(row)

            export_table(
                pd.DataFrame(rows),
                f"12_{mode}_water_UA_x_flow_fixed_load",
                "WaterUAFlow",
            )

    # Air UA x water UA.
    if RUN_AIR_UA_X_WATER_UA:
        for mode in ("heating", "cooling"):
            rows = []

            for air_ua in config.AIR_UA_FINE_MULTIPLIERS:
                for water_ua in config.WATER_UA_FINE_MULTIPLIERS:
                    rows.append(
                        fixed_load_result(
                            model,
                            calibrations,
                            mode,
                            targets[mode],
                            air_UA_multiplier=air_ua,
                            water_UA_multiplier=water_ua,
                        )
                    )

            export_table(
                pd.DataFrame(rows),
                f"13_{mode}_air_UA_x_water_UA_fixed_load",
                "AirWaterUA",
            )


# ============================================================
# 9. SUMMARY
# ============================================================

def create_summary(model, calibrations, targets):
    rows = []

    for mode in ("heating", "cooling"):
        baseline = fixed_load_result(
            model,
            calibrations,
            mode,
            targets[mode],
        )

        rows.append({
            "mode": mode,
            "reference_outdoor_C": baseline.get("outdoor_C"),
            "reference_water_out_C": baseline.get("water_out_C"),
            "reference_target_Q_kW": targets[mode],
            "reference_frequency_Hz": baseline.get("frequency_Hz"),
            "reference_COP_or_EER": baseline.get("COP_or_EER_circuit"),
            "reference_fan_speed_fraction": baseline.get("fan_speed_fraction"),
            "calibration_source": calibrations[mode].source,
        })

    export_table(
        pd.DataFrame(rows),
        "00_parametric_reference_points",
        "Reference",
    )


# ============================================================
# 10. MAIN
# ============================================================

def main():
    model, calibrations = build_model()

    targets = {
        mode: baseline_target(
            model,
            calibrations,
            mode,
        )
        for mode in ("heating", "cooling")
    }

    create_summary(
        model,
        calibrations,
        targets,
    )

    create_1d_studies(
        model,
        calibrations,
        targets,
    )

    create_2d_studies(
        model,
        calibrations,
        targets,
    )

    pass
    pass
    pass


if __name__ == "__main__":
    main()
