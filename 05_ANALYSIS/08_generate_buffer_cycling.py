"""
08_generate_buffer_cycling.py

Ideal low-load buffer-tank cycling sensitivity.

No plots are created here.

The model is intentionally simple and transparent:
- heat pump output during ON operation = minimum one-circuit HERA capacity;
- building load is constant during each cycle;
- tank is lossless;
- usable storage = V * rho * cp * deadband.

The result is a screening analysis, not a transient controller simulation.
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

INPUT_FRASCOLD_DATABASE = (
    PROJECT_ROOT / "06_RESULTS" / "databases" / "frascold_performance_grid.csv"
)

INPUT_HX_CALIBRATION = (
    PROJECT_ROOT / "06_RESULTS" / "databases" / "hera_hx_calibration.csv"
)

OUTPUT_FOLDER = (
    PROJECT_ROOT / "06_RESULTS" / "optimization" / "buffer"
)


# ============================================================
# 3. CHANGEABLE SETTINGS
# ============================================================

# Approximate fluid properties used only for the ideal buffer energy balance.
# Change here if a different mixture property should be used.
BUFFER_DENSITY_KG_M3 = 1030.0
BUFFER_CP_KJ_KGK = 3.80


# ============================================================
# 4. MODULE LOADING
# ============================================================

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


config = load_module("config_buffer_v2", CONFIG_FILE)
table_io = load_module("table_io_buffer_v2", TABLE_IO_FILE)
grid_module = load_module("frascold_grid_buffer_v2", FRASCOLD_GRID_MODEL_FILE)
hera_module = load_module("hera_buffer_v2", HERA_MODEL_FILE)
factory = load_module("factory_buffer_v2", MODEL_FACTORY_FILE)
plant = load_module("plant_buffer_v2", PLANT_MODEL_FILE)


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
# 6. MINIMUM CAPACITY FROM HERA MODEL
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


def minimum_one_circuit_capacity(
    model,
    calibrations,
    mode,
):
    if mode == "heating":
        outdoor_C = config.ANALYTIC_HEATING_OUTDOOR_C
        water_out_C = config.HEATING_WATER_OUT_C
    else:
        outdoor_C = config.ANALYTIC_COOLING_OUTDOOR_C
        water_out_C = config.COOLING_WATER_OUT_C

    result = model.safe_evaluate(
        hera_module.CircuitCase(
            mode=mode,
            outdoor_C=outdoor_C,
            water_out_C=water_out_C,
            frequency_Hz=config.FREQUENCY_MIN_HZ,
            fan_speed_fraction=(
                calibrations[mode].reference_fan_speed_fraction
            ),
        )
    )

    if result.get("model_status") != "OK":
        raise RuntimeError(
            f"Could not determine {mode} Qmin: {result.get('model_error')}"
        )

    return {
        "mode": mode,
        "outdoor_C": outdoor_C,
        "water_out_C": water_out_C,
        "minimum_frequency_Hz": config.FREQUENCY_MIN_HZ,
        "minimum_one_circuit_capacity_kW": float(result["Quseful_kW"]),
    }


# ============================================================
# 7. BUFFER STUDY
# ============================================================

def main():
    model, calibrations = build_model()

    qmin_rows = [
        minimum_one_circuit_capacity(
            model,
            calibrations,
            mode,
        )
        for mode in ("heating", "cooling")
    ]

    qmin_table = pd.DataFrame(qmin_rows)

    export_table(
        qmin_table,
        "00_buffer_Qmin_reference",
        "Qmin",
    )

    rows = []

    for qmin_row in qmin_rows:
        mode = qmin_row["mode"]
        qmin = qmin_row["minimum_one_circuit_capacity_kW"]

        volumes = (
            config.BUFFER_HEATING_VOLUME_STUDY_L
            if mode == "heating"
            else config.BUFFER_COOLING_VOLUME_STUDY_L
        )

        installed_volume = (
            config.BUFFER_TANK_HEATING_INSTALLED_L
            if mode == "heating"
            else config.BUFFER_TANK_COOLING_INSTALLED_L
        )

        for volume in volumes:
            for load_fraction in config.BUFFER_LOAD_FRACTIONS_OF_QMIN:
                result = plant.ideal_buffer_cycle(
                    minimum_heat_pump_capacity_kW=qmin,
                    average_building_load_kW=qmin * load_fraction,
                    volume_L=volume,
                    deadband_K=config.BUFFER_DEADBAND_K,
                    density_kg_m3=BUFFER_DENSITY_KG_M3,
                    cp_kJ_kgK=BUFFER_CP_KJ_KGK,
                )

                result["mode"] = mode
                result["installed_volume_reference_L"] = installed_volume
                result["is_installed_volume"] = bool(
                    np.isclose(volume, installed_volume)
                )
                result["outdoor_C"] = qmin_row["outdoor_C"]
                result["water_out_C"] = qmin_row["water_out_C"]
                rows.append(result)

    study = pd.DataFrame(rows)

    export_table(
        study,
        "01_buffer_cycling_sensitivity",
        "BufferCycling",
    )

    pass


if __name__ == "__main__":
    main()
