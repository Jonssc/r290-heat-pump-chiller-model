"""
07_generate_circuit_and_plant_dispatch.py

Generates reusable circuit-staging and 1/2/3-HERA plant-dispatch tables.

No plots are created here.

The analysis distinguishes:
- one active refrigerant circuit,
- two active refrigerant circuits,
rather than treating physical C2 as inherently the "second stage".
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
    PROJECT_ROOT / "06_RESULTS" / "optimization" / "dispatch"
)


# ============================================================
# 3. ANALYSIS SELECTION
# ============================================================

GENERATE_CHILLER_ONLY_BOUNDARY = True
GENERATE_WITH_UNIT_PUMP_SCREENING = True

GENERATE_ONE_VS_TWO_CIRCUITS = True
GENERATE_SECOND_CIRCUIT_STRATEGIES = False
GENERATE_ONE_TWO_THREE_HERA_DISPATCH = True


# ============================================================
# 4. CHANGEABLE OPERATING CONDITIONS
# ============================================================

# Loaded from config.py after module import.
HEATING_OUTDOOR_C = 7.0
COOLING_OUTDOOR_C = 35.0

# The actual water targets are read from config.py:
# heating = 50 °C, cooling = 7 °C by default.

LOAD_STEP_KW = 5.0


# ============================================================
# 5. MODULE LOADING
# ============================================================

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


config = load_module("config_dispatch_v2", CONFIG_FILE)
table_io = load_module("table_io_dispatch_v2", TABLE_IO_FILE)
grid_module = load_module("frascold_grid_dispatch_v2", FRASCOLD_GRID_MODEL_FILE)
hera_module = load_module("hera_dispatch_v2", HERA_MODEL_FILE)
factory = load_module("factory_dispatch_v2", MODEL_FACTORY_FILE)
plant = load_module("plant_dispatch_v2", PLANT_MODEL_FILE)

HEATING_OUTDOOR_C = config.ANALYTIC_HEATING_OUTDOOR_C
COOLING_OUTDOOR_C = config.ANALYTIC_COOLING_OUTDOOR_C
LOAD_STEP_KW = config.DISPATCH_LOAD_STEP_KW


# ============================================================
# 6. OUTPUT HELPER
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
# 7. MODEL CONSTRUCTION
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


def maximum_unit_capacity(model, calibrations, mode, outdoor_C, water_out_C):
    fan = calibrations[mode].reference_fan_speed_fraction

    result = model.safe_evaluate(
        hera_module.CircuitCase(
            mode=mode,
            outdoor_C=outdoor_C,
            water_out_C=water_out_C,
            frequency_Hz=config.FREQUENCY_MAX_HZ,
            fan_speed_fraction=fan,
        )
    )

    if result.get("model_status") != "OK":
        raise RuntimeError(
            f"Could not determine {mode} maximum capacity: "
            f"{result.get('model_error')}"
        )

    return 2.0 * float(result["Quseful_kW"])


# ============================================================
# 8. EXACT-N PLANT DISPATCH HELPERS
# ============================================================

def first_exact_dispatch_advantage(
    exact_tables,
    challenger,
    *,
    minimum_advantage_kW=0.10,
):
    """First plant load where exactly N units beat every lower-N option."""
    challenger = int(challenger)
    ch = exact_tables.get(challenger, pd.DataFrame())
    if ch.empty:
        return None

    merged = ch[["total_load_kW", "plant_power_kW"]].rename(
        columns={"plant_power_kW": "challenger_power_kW"}
    )

    lower_power_columns = []

    for n_units in range(1, challenger):
        lower = exact_tables.get(n_units, pd.DataFrame())
        if lower.empty:
            continue
        column = f"power_{n_units}_units_kW"
        lower_power_columns.append(column)
        merged = merged.merge(
            lower[["total_load_kW", "plant_power_kW"]].rename(
                columns={"plant_power_kW": column}
            ),
            on="total_load_kW",
            how="left",
        )

    if merged.empty or not lower_power_columns:
        return None

    lower_best = merged[lower_power_columns].min(axis=1, skipna=True)
    advantage = lower_best - merged["challenger_power_kW"]
    better = lower_best.notna() & (
        advantage > float(minimum_advantage_kW)
    )

    if not better.any():
        return None

    return float(merged.loc[better, "total_load_kW"].iloc[0])


# ============================================================
# 9. ONE ANALYSIS BOUNDARY
# ============================================================

def run_boundary(
    model,
    calibrations,
    *,
    boundary_name,
    include_unit_pump,
    configuration_cache,
):
    boundary_rows = []

    mode_conditions = {
        "heating": (
            HEATING_OUTDOOR_C,
            config.HEATING_WATER_OUT_C,
        ),
        "cooling": (
            COOLING_OUTDOOR_C,
            config.COOLING_WATER_OUT_C,
        ),
    }

    for mode, (outdoor_C, water_out_C) in mode_conditions.items():
        max_capacity = maximum_unit_capacity(
            model,
            calibrations,
            mode,
            outdoor_C,
            water_out_C,
        )

        unit_loads = np.arange(
            LOAD_STEP_KW,
            max_capacity + 0.5 * LOAD_STEP_KW,
            LOAD_STEP_KW,
        )

        # The thermodynamic solution is identical for the chiller-only and
        # unit-pump-screening electrical boundaries. Solve it only once per
        # mode/load grid, then add the constant per-unit pump screening power
        # algebraically. This makes fine dispatch load increments practical
        # without changing the thermodynamic result.
        cache_key = (
            mode,
            float(outdoor_C),
            float(water_out_C),
            float(LOAD_STEP_KW),
        )

        if cache_key not in configuration_cache:
            configuration_cache[cache_key] = plant.build_unit_configuration_table(
                model,
                mode,
                outdoor_C,
                water_out_C,
                unit_loads,
                config.DISPATCH_FAN_CANDIDATES,
                include_unit_pump=False,
                frequency_seed_Hz=config.ANALYTIC_REFERENCE_FREQUENCY_HZ,
            )

        configuration = configuration_cache[cache_key].copy()

        if include_unit_pump:
            pump_power_kW = plant.unit_pump_power_kW(
                1.0,
                config.UNIT_PUMP_ELECTRICAL_REFERENCE_KW,
                motor_load_factor=config.PUMP_MOTOR_LOAD_FACTOR,
                power_exponent=config.PUMP_POWER_EXPONENT,
            )
            configuration["unit_pump_power_kW"] = pump_power_kW
            configuration["unit_total_power_kW"] = (
                pd.to_numeric(
                    configuration["unit_chiller_power_kW"],
                    errors="coerce",
                )
                + pump_power_kW
            )
            configuration["unit_COP_or_EER"] = (
                pd.to_numeric(configuration["unit_load_kW"], errors="coerce")
                / configuration["unit_total_power_kW"]
            )
        else:
            configuration["unit_pump_power_kW"] = 0.0
            configuration["unit_total_power_kW"] = configuration[
                "unit_chiller_power_kW"
            ]
            configuration["unit_COP_or_EER"] = (
                pd.to_numeric(configuration["unit_load_kW"], errors="coerce")
                / configuration["unit_total_power_kW"]
            )

        configuration["electrical_boundary"] = boundary_name

        if GENERATE_ONE_VS_TWO_CIRCUITS:
            export_table(
                configuration,
                f"01_{mode}_one_vs_two_circuits_{boundary_name}",
                "CircuitComparison",
            )

        best = plant.select_best_unit_envelope(
            configuration
        )

        best["electrical_boundary"] = boundary_name

        # Second-circuit switch strategies.
        if GENERATE_SECOND_CIRCUIT_STRATEGIES:
            switch = plant.first_lower_power_load(
                configuration,
                challenger=2,
                incumbent=1,
                minimum_advantage_kW=(
                    config.SECOND_CIRCUIT_SWITCH_POWER_ADVANTAGE_KW
                ),
            )

            delayed = plant.build_switch_strategy_curve(
                configuration,
                None,
            )

            delayed["electrical_boundary"] = boundary_name

            export_table(
                delayed,
                f"03_{mode}_second_circuit_delayed_reference_{boundary_name}",
                "DelayedStrategy",
            )

            if switch is not None:
                efficient = plant.build_switch_strategy_curve(
                    configuration,
                    switch,
                )

                efficient["electrical_boundary"] = boundary_name

                export_table(
                    efficient,
                    f"04_{mode}_second_circuit_efficiency_strategy_{boundary_name}",
                    "EfficiencyStrategy",
                )

                merge = delayed[
                    [
                        "unit_load_kW",
                        "unit_total_power_kW",
                        "unit_COP_or_EER",
                    ]
                ].rename(
                    columns={
                        "unit_total_power_kW": "delayed_power_kW",
                        "unit_COP_or_EER": "delayed_COP_or_EER",
                    }
                ).merge(
                    efficient[
                        [
                            "unit_load_kW",
                            "unit_total_power_kW",
                            "unit_COP_or_EER",
                        ]
                    ].rename(
                        columns={
                            "unit_total_power_kW": "efficient_power_kW",
                            "unit_COP_or_EER": "efficient_COP_or_EER",
                        }
                    ),
                    on="unit_load_kW",
                    how="outer",
                )

                merge["power_saving_kW"] = (
                    merge["delayed_power_kW"]
                    - merge["efficient_power_kW"]
                )

                merge["COP_or_EER_gain"] = (
                    merge["efficient_COP_or_EER"]
                    - merge["delayed_COP_or_EER"]
                )

                merge["efficiency_switch_load_kW"] = switch
                merge["electrical_boundary"] = boundary_name

                export_table(
                    merge,
                    f"05_{mode}_second_circuit_strategy_comparison_{boundary_name}",
                    "StrategyComparison",
                )

        # Plant dispatch using the already-calculated best unit table.
        #
        # V2 now restores the older exact-N method for the 1/2/3-unit
        # comparison: for every plant load, the load distribution between
        # exactly 1, exactly 2, or exactly 3 active physical Chiller Units is
        # optimized independently. Equal unit loading is NOT imposed.
        if GENERATE_ONE_TWO_THREE_HERA_DISPATCH:
            exact_tables = {}

            for n_units in range(1, config.NUMBER_OF_HERA_UNITS + 1):
                exact = plant.exact_n_unit_dispatch_from_unit_table(
                    best,
                    n_units=n_units,
                    load_step_kW=LOAD_STEP_KW,
                )

                if exact.empty:
                    continue

                exact["mode"] = mode
                exact["electrical_boundary"] = boundary_name
                exact["outdoor_C"] = outdoor_C
                exact["water_out_C"] = water_out_C
                exact_tables[n_units] = exact

                export_table(
                    exact,
                    f"{6+n_units:02d}_{mode}_exact_{n_units}_active_units_{boundary_name}",
                    f"Exact{n_units}Units",
                )

            # The selected plant envelope is now explicitly built from the
            # exact 1/2/3-unit curves. This is mathematically the same decision
            # problem as the previous up-to-three-unit dispatch, but it keeps
            # the exact alternatives available for transparent comparison.
            dispatch = plant.selected_exact_dispatch_envelope(
                exact_tables
            )

            if not dispatch.empty:
                dispatch = dispatch.rename(
                    columns={"active_units": "optimal_active_units"}
                )
                dispatch["mode"] = mode
                dispatch["electrical_boundary"] = boundary_name
                dispatch["outdoor_C"] = outdoor_C
                dispatch["water_out_C"] = water_out_C

                export_table(
                    dispatch,
                    f"06_{mode}_one_two_three_HERA_dispatch_{boundary_name}",
                    "PlantDispatch",
                )

            crossover_rows = []
            for challenger in range(2, config.NUMBER_OF_HERA_UNITS + 1):
                crossover = first_exact_dispatch_advantage(
                    exact_tables,
                    challenger,
                    minimum_advantage_kW=0.10,
                )
                crossover_rows.append({
                    "mode": mode,
                    "electrical_boundary": boundary_name,
                    "challenger_active_units": challenger,
                    "compared_against_active_units": "; ".join(
                        str(n) for n in range(1, challenger)
                    ),
                    "crossover_load_kW": crossover,
                    "minimum_power_advantage_kW": 0.10,
                    "outdoor_C": outdoor_C,
                    "water_out_C": water_out_C,
                    "load_step_kW": LOAD_STEP_KW,
                })

            export_table(
                pd.DataFrame(crossover_rows),
                f"11_{mode}_exact_unit_crossover_summary_{boundary_name}",
                "Crossovers",
            )

        boundary_rows.append({
            "mode": mode,
            "electrical_boundary": boundary_name,
            "outdoor_C": outdoor_C,
            "water_out_C": water_out_C,
            "maximum_one_HERA_capacity_kW": max_capacity,
            "unit_load_step_kW": LOAD_STEP_KW,
            "pump_included": include_unit_pump,
        })

    return boundary_rows


# ============================================================
# 10. MAIN
# ============================================================

def main():
    model, calibrations = build_model()

    summary_rows = []
    configuration_cache = {}

    if GENERATE_CHILLER_ONLY_BOUNDARY:
        summary_rows.extend(
            run_boundary(
                model,
                calibrations,
                boundary_name="chiller_only",
                include_unit_pump=False,
                configuration_cache=configuration_cache,
            )
        )

    if GENERATE_WITH_UNIT_PUMP_SCREENING:
        summary_rows.extend(
            run_boundary(
                model,
                calibrations,
                boundary_name="with_unit_pump_screening",
                include_unit_pump=True,
                configuration_cache=configuration_cache,
            )
        )

    export_table(
        pd.DataFrame(summary_rows),
        "00_dispatch_analysis_settings",
        "Settings",
    )



if __name__ == "__main__":
    main()
