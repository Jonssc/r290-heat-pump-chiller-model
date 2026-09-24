"""
17_mixed_unit_sizing.py

Hypothetical one-small + two-full-size HERA sizing sensitivity.

Method retained from the previous validated study:
- February...July 2026 measured/classifiable branch data;
- loads below 5 kW treated as inactive;
- only active plant operation evaluated;
- 5 kW load bins;
- 1 K outdoor/heating-water/cooling-water bins;
- 2.5 Hz compressor grid;
- reference fleet = 3 x 100%;
- candidate fleet = 1 x scaled + 2 x 100%;
- small-unit size sweep = 2.5 percentage-point increments;
- geometric capacity/power scaling;
- Cd = 0.15 central case plus 0.025-step sensitivity.

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

CONFIG_FILE = (
    PROJECT_ROOT
    / "00_CONFIG"
    / "config.py"
)

TABLE_IO_FILE = (
    PROJECT_ROOT
    / "00_CONFIG"
    / "table_io.py"
)

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

ANNUAL_PLANT_MODEL_FILE = (
    PROJECT_ROOT
    / "03_MODELS"
    / "annual_plant_model.py"
)

MIXED_FLEET_MODEL_FILE = (
    PROJECT_ROOT
    / "03_MODELS"
    / "mixed_fleet_model.py"
)

INPUT_CLASSIFIED_POINTS = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "annual"
    / "hybrid_classified_points.csv"
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

OUTPUT_SIZE_SWEEP = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "optimization"
    / "mixed_sizing"
    / "mixed_unit_size_sweep"
)

OUTPUT_CYCLING_SENSITIVITY = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "optimization"
    / "mixed_sizing"
    / "mixed_unit_cycling_sensitivity"
)

OUTPUT_SUMMARY = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "optimization"
    / "mixed_sizing"
    / "mixed_unit_summary"
)


# ============================================================
# 3. MODULE LOADING
# ============================================================

def load_module(
    name,
    path,
):
    spec = importlib.util.spec_from_file_location(
        name,
        path,
    )

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[
        name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


config = load_module(
    "config_mixed_v2",
    CONFIG_FILE,
)

table_io = load_module(
    "table_io_mixed_v2",
    TABLE_IO_FILE,
)

grid_module = load_module(
    "grid_mixed_v2",
    FRASCOLD_GRID_MODEL_FILE,
)

hera_module = load_module(
    "hera_mixed_v2",
    HERA_MODEL_FILE,
)

factory = load_module(
    "factory_mixed_v2",
    MODEL_FACTORY_FILE,
)

annual_model = load_module(
    "annual_model_mixed_v2",
    ANNUAL_PLANT_MODEL_FILE,
)

mixed_model = load_module(
    "mixed_fleet_v2",
    MIXED_FLEET_MODEL_FILE,
)


# ============================================================
# 4. MODEL CONSTRUCTION
# ============================================================

def build_model():
    return factory.build_circuit_model(
        frascold_database=INPUT_FRASCOLD_DATABASE,
        calibration_file=INPUT_HX_CALIBRATION,
        config=config,
        table_io=table_io,
        frascold_grid_module=grid_module,
        hera_module=hera_module,
        air_ht_exponent_override=(
            config.ANNUAL_AIR_HT_EXPONENT
        ),
    )


# ============================================================
# 5. SOURCE DATA PREPARATION
# ============================================================

def round_to_step(
    series,
    step,
):
    return (
        pd.to_numeric(
            series,
            errors="coerce",
        )
        / float(
            step
        )
    ).round() * float(
        step
    )


def prepare_measured_bins():
    if not INPUT_CLASSIFIED_POINTS.exists():
        raise FileNotFoundError(
            "Run 14_hybrid_operation.py first."
        )

    data = table_io.read_table(
        INPUT_CLASSIFIED_POINTS
    )

    data["timestamp"] = pd.to_datetime(
        data["timestamp"],
        errors="coerce",
    )

    start = pd.Timestamp(
        year=config.HYBRID_START_YEAR,
        month=config.HYBRID_START_MONTH,
        day=1,
    )

    end = (
        pd.Timestamp(
            year=config.HYBRID_END_YEAR,
            month=config.HYBRID_END_MONTH,
            day=1,
        )
        + pd.offsets.MonthBegin(1)
    )

    data = data[
        (
            data["timestamp"]
            >= start
        )
        & (
            data["timestamp"]
            < end
        )
        & data["Operating_state"].isin(
            [
                "Heating only",
                "Cooling only",
                "Hybrid",
                "Inactive / low load",
            ]
        )
    ].copy()

    data["Heating_load_kW"] = pd.to_numeric(
        data[
            "Heating_load_filtered_kW"
        ],
        errors="coerce",
    )

    data["Cooling_load_kW"] = pd.to_numeric(
        data[
            "Cooling_load_filtered_kW"
        ],
        errors="coerce",
    )

    data.loc[
        data["Heating_load_kW"]
        < config.MIXED_ACTIVE_LOAD_THRESHOLD_KW,
        "Heating_load_kW",
    ] = 0.0

    data.loc[
        data["Cooling_load_kW"]
        < config.MIXED_ACTIVE_LOAD_THRESHOLD_KW,
        "Cooling_load_kW",
    ] = 0.0

    data = data[
        (
            data["Heating_load_kW"] > 0
        )
        | (
            data["Cooling_load_kW"] > 0
        )
    ].copy()

    data = data.dropna(
        subset=[
            "Outdoor_C",
            "RT403_C",
            "RT404_C",
        ]
    )

    data["Heating_load_bin_kW"] = round_to_step(
        data[
            "Heating_load_kW"
        ],
        config.MIXED_MODEL_LOAD_BIN_KW,
    )

    data["Cooling_load_bin_kW"] = round_to_step(
        data[
            "Cooling_load_kW"
        ],
        config.MIXED_MODEL_LOAD_BIN_KW,
    )

    data["Outdoor_bin_C"] = round_to_step(
        data[
            "Outdoor_C"
        ],
        config.MIXED_MODEL_TEMPERATURE_BIN_K,
    )

    data["Heating_water_bin_C"] = round_to_step(
        data[
            "RT403_C"
        ],
        config.MIXED_MODEL_TEMPERATURE_BIN_K,
    )

    data["Cooling_water_bin_C"] = round_to_step(
        data[
            "RT404_C"
        ],
        config.MIXED_MODEL_TEMPERATURE_BIN_K,
    )

    data["month"] = (
        data[
            "timestamp"
        ]
        .dt.to_period(
            "M"
        )
        .astype(str)
    )

    # Month and state do not affect the thermodynamic dispatch. Combine
    # identical numerical operating bins here to avoid repeating the same
    # calculation. This gives the same weighted energy result as the previous
    # month/state-separated grouping.
    grouped = (
        data
        .groupby(
            [
                "Heating_load_bin_kW",
                "Cooling_load_bin_kW",
                "Outdoor_bin_C",
                "Heating_water_bin_C",
                "Cooling_water_bin_C",
            ]
        )
        .agg(
            sample_count=(
                "timestamp",
                "size",
            )
        )
        .reset_index()
    )

    grouped[
        "represented_hours"
    ] = (
        grouped[
            "sample_count"
        ]
        * config.SOURCE_TIMESTEP_MINUTES
        / 60.0
    )

    return grouped


# ============================================================
# 6. FLEET DISPATCH
# ============================================================

def dispatch_fleet(
    circuit_model,
    fleet,
    heating_load_kW,
    cooling_load_kW,
    outdoor_C,
    heating_water_C,
    cooling_water_C,
    Cd,
):
    return mixed_model.dispatch_scaled_fleet(
        annual_model,
        circuit_model,
        unit_size_factors=fleet,
        heating_load_kW=float(
            heating_load_kW
        ),
        cooling_load_kW=float(
            cooling_load_kW
        ),
        outdoor_C=float(
            outdoor_C
        ),
        heating_water_out_C=float(
            heating_water_C
        ),
        cooling_water_out_C=float(
            cooling_water_C
        ),
        cycling_degradation_coefficient=float(
            Cd
        ),
        frequency_step_Hz=(
            config.MIXED_MODEL_FREQUENCY_STEP_HZ
        ),
    )


# ============================================================
# 7. REFERENCE DISPATCH
# ============================================================

def build_reference(
    bins,
    circuit_model,
    Cd,
):
    rows = []

    for row in bins.itertuples(
        index=False
    ):
        result = dispatch_fleet(
            circuit_model,
            tuple(
                config.MIXED_REFERENCE_FLEET
            ),
            row.Heating_load_bin_kW,
            row.Cooling_load_bin_kW,
            row.Outdoor_bin_C,
            row.Heating_water_bin_C,
            row.Cooling_water_bin_C,
            Cd,
        )

        record = {
            "Heating_load_kW": float(
                row.Heating_load_bin_kW
            ),
            "Cooling_load_kW": float(
                row.Cooling_load_bin_kW
            ),
            "Outdoor_C": float(
                row.Outdoor_bin_C
            ),
            "Heating_water_C": float(
                row.Heating_water_bin_C
            ),
            "Cooling_water_C": float(
                row.Cooling_water_bin_C
            ),
            "represented_hours": float(
                row.represented_hours
            ),
        }

        feasible = (
            result.get(
                "model_status"
            )
            == "OK"
            and float(
                result.get(
                    "total_shortfall_kW",
                    0.0,
                )
            )
            <= 1e-9
        )

        if feasible:
            record[
                "reference_status"
            ] = "OK"

            record[
                "reference_power_kW"
            ] = float(
                result[
                    "plant_power_kW"
                ]
            )

            record[
                "reference_heating_cycling"
            ] = bool(
                result.get(
                    "heating_cycling",
                    False,
                )
            )

            record[
                "reference_cooling_cycling"
            ] = bool(
                result.get(
                    "cooling_cycling",
                    False,
                )
            )

        else:
            record[
                "reference_status"
            ] = "INFEASIBLE"

        rows.append(
            record
        )

    return pd.DataFrame(
        rows
    )


# ============================================================
# 8. SMALL-UNIT SIZE SWEEP
# ============================================================

def size_sweep(
    reference_valid,
    circuit_model,
    Cd,
):
    reference_valid_hours = float(
        reference_valid[
            "represented_hours"
        ].sum()
    )

    rows = []

    for size_factor in config.MIXED_SMALL_UNIT_SIZE_FACTORS:
        fleet = (
            float(
                size_factor
            ),
            1.0,
            1.0,
        )

        baseline_energy_kWh = 0.0
        mixed_energy_kWh = 0.0

        candidate_feasible_hours = 0.0
        candidate_infeasible_hours = 0.0

        reference_heating_cycling_hours = 0.0
        reference_cooling_cycling_hours = 0.0

        mixed_heating_cycling_hours = 0.0
        mixed_cooling_cycling_hours = 0.0

        for row in reference_valid.itertuples(
            index=False
        ):
            represented_hours = float(
                row.represented_hours
            )

            candidate = dispatch_fleet(
                circuit_model,
                fleet,
                row.Heating_load_kW,
                row.Cooling_load_kW,
                row.Outdoor_C,
                row.Heating_water_C,
                row.Cooling_water_C,
                Cd,
            )

            feasible = (
                candidate.get(
                    "model_status"
                )
                == "OK"
                and float(
                    candidate.get(
                        "total_shortfall_kW",
                        0.0,
                    )
                )
                <= 1e-9
            )

            if not feasible:
                candidate_infeasible_hours += (
                    represented_hours
                )
                continue

            candidate_feasible_hours += (
                represented_hours
            )

            baseline_energy_kWh += (
                float(
                    row.reference_power_kW
                )
                * represented_hours
            )

            mixed_energy_kWh += (
                float(
                    candidate[
                        "plant_power_kW"
                    ]
                )
                * represented_hours
            )

            if bool(
                row.reference_heating_cycling
            ):
                reference_heating_cycling_hours += (
                    represented_hours
                )

            if bool(
                row.reference_cooling_cycling
            ):
                reference_cooling_cycling_hours += (
                    represented_hours
                )

            if bool(
                candidate.get(
                    "heating_cycling",
                    False,
                )
            ):
                mixed_heating_cycling_hours += (
                    represented_hours
                )

            if bool(
                candidate.get(
                    "cooling_cycling",
                    False,
                )
            ):
                mixed_cooling_cycling_hours += (
                    represented_hours
                )

        coverage = (
            100.0
            * candidate_feasible_hours
            / reference_valid_hours
            if reference_valid_hours > 0
            else np.nan
        )

        reference_MWh = (
            baseline_energy_kWh
            / 1000.0
        )

        mixed_MWh = (
            mixed_energy_kWh
            / 1000.0
        )

        saving_MWh = (
            reference_MWh
            - mixed_MWh
        )

        rows.append({
            "small_unit_size_factor": float(
                size_factor
            ),
            "small_unit_percent_of_existing": (
                100.0
                * float(
                    size_factor
                )
            ),
            "fleet_description": (
                f"1 x {100*size_factor:.0f}% + 2 x 100% HERA"
            ),
            "reference_valid_hours": reference_valid_hours,
            "candidate_feasible_hours": candidate_feasible_hours,
            "coverage_of_reference_percent": coverage,
            "candidate_infeasible_hours": candidate_infeasible_hours,
            "peak_feasible": bool(
                candidate_infeasible_hours <= 1e-12
                if config.MIXED_REQUIRE_100_PERCENT_REFERENCE_COVERAGE
                else coverage >= 99.5
            ),
            "reference_electricity_MWh": reference_MWh,
            "mixed_electricity_MWh": mixed_MWh,
            "electrical_saving_MWh": saving_MWh,
            "electrical_saving_percent": (
                100.0
                * saving_MWh
                / reference_MWh
                if reference_MWh > 0
                else np.nan
            ),
            "reference_heating_cycling_hours": (
                reference_heating_cycling_hours
            ),
            "mixed_heating_cycling_hours": (
                mixed_heating_cycling_hours
            ),
            "heating_cycling_reduction_hours": (
                reference_heating_cycling_hours
                - mixed_heating_cycling_hours
            ),
            "reference_cooling_cycling_hours": (
                reference_cooling_cycling_hours
            ),
            "mixed_cooling_cycling_hours": (
                mixed_cooling_cycling_hours
            ),
            "cooling_cycling_reduction_hours": (
                reference_cooling_cycling_hours
                - mixed_cooling_cycling_hours
            ),
        })

    return pd.DataFrame(
        rows
    )


# ============================================================
# 9. ONE CANDIDATE AGAINST AN EXISTING REFERENCE
# ============================================================

def evaluate_one_size(
    reference_valid,
    circuit_model,
    Cd,
    size_factor,
):
    """Evaluate one mixed-fleet size without recalculating the whole size sweep."""

    fleet = (
        float(size_factor),
        1.0,
        1.0,
    )

    reference_energy_kWh = 0.0
    mixed_energy_kWh = 0.0

    candidate_feasible_hours = 0.0
    candidate_infeasible_hours = 0.0

    for row in reference_valid.itertuples(
        index=False
    ):
        represented_hours = float(
            row.represented_hours
        )

        candidate = dispatch_fleet(
            circuit_model,
            fleet,
            row.Heating_load_kW,
            row.Cooling_load_kW,
            row.Outdoor_C,
            row.Heating_water_C,
            row.Cooling_water_C,
            Cd,
        )

        feasible = (
            candidate.get(
                "model_status"
            )
            == "OK"
            and float(
                candidate.get(
                    "total_shortfall_kW",
                    0.0,
                )
            )
            <= 1e-9
        )

        if not feasible:
            candidate_infeasible_hours += (
                represented_hours
            )
            continue

        candidate_feasible_hours += (
            represented_hours
        )

        reference_energy_kWh += (
            float(
                row.reference_power_kW
            )
            * represented_hours
        )

        mixed_energy_kWh += (
            float(
                candidate[
                    "plant_power_kW"
                ]
            )
            * represented_hours
        )

    reference_MWh = (
        reference_energy_kWh
        / 1000.0
    )

    mixed_MWh = (
        mixed_energy_kWh
        / 1000.0
    )

    saving_MWh = (
        reference_MWh
        - mixed_MWh
    )

    return {
        "small_unit_size_factor":
            float(
                size_factor
            ),
        "candidate_feasible_hours":
            candidate_feasible_hours,
        "candidate_infeasible_hours":
            candidate_infeasible_hours,
        "reference_electricity_MWh":
            reference_MWh,
        "mixed_electricity_MWh":
            mixed_MWh,
        "electrical_saving_MWh":
            saving_MWh,
        "electrical_saving_percent": (
            100.0
            * saving_MWh
            / reference_MWh
            if reference_MWh > 0
            else np.nan
        ),
    }


# ============================================================
# 10. CYCLING-DEGRADATION SENSITIVITY
# ============================================================

def cycling_sensitivity(
    bins,
    circuit_model,
    selected_size,
):
    rows = []

    for Cd in config.MIXED_CYCLING_DEGRADATION_SENSITIVITY:
        reference = build_reference(
            bins,
            circuit_model,
            Cd,
        )

        reference_valid = reference[
            reference[
                "reference_status"
            ]
            == "OK"
        ].copy()

        result = evaluate_one_size(
            reference_valid,
            circuit_model,
            Cd,
            selected_size,
        )

        rows.append({
            "cycling_degradation_coefficient":
                Cd,
            "small_unit_size_factor":
                selected_size,
            "reference_electricity_MWh":
                result[
                    "reference_electricity_MWh"
                ],
            "mixed_electricity_MWh":
                result[
                    "mixed_electricity_MWh"
                ],
            "electrical_saving_MWh":
                result[
                    "electrical_saving_MWh"
                ],
            "electrical_saving_percent":
                result[
                    "electrical_saving_percent"
                ],
        })

    return pd.DataFrame(
        rows
    )


# ============================================================
# 11. EXPORT
# ============================================================

def export_table(
    dataframe,
    output,
    sheet_name,
):
    table_io.write_table(
        dataframe,
        output,
        export_csv=config.EXPORT_CSV,
        export_xlsx=config.EXPORT_XLSX,
        csv_separator=config.CSV_SEPARATOR,
        csv_decimal=config.CSV_DECIMAL,
        float_format=config.CSV_FLOAT_FORMAT,
        sheet_name=sheet_name,
    )


# ============================================================
# 12. MAIN
# ============================================================

def main():
    bins = prepare_measured_bins()

    circuit_model, calibrations = build_model()

    reference = build_reference(
        bins,
        circuit_model,
        config.MIXED_CYCLING_DEGRADATION_COEFFICIENT,
    )

    reference_valid = reference[
        reference[
            "reference_status"
        ]
        == "OK"
    ].copy()

    sweep = size_sweep(
        reference_valid,
        circuit_model,
        config.MIXED_CYCLING_DEGRADATION_COEFFICIENT,
    )

    feasible = sweep[
        sweep[
            "peak_feasible"
        ].astype(bool)
    ]

    if feasible.empty:
        selected = sweep.loc[
            sweep[
                "coverage_of_reference_percent"
            ].idxmax()
        ]

    else:
        maximum_saving = feasible[
            "electrical_saving_percent"
        ].max()

        # If energy savings are essentially flat, prefer the smaller
        # peak-feasible machine instead of a trivially larger one.
        near_best = feasible[
            feasible[
                "electrical_saving_percent"
            ]
            >= maximum_saving - 0.10
        ]

        selected = near_best.sort_values(
            "small_unit_size_factor"
        ).iloc[0]

    sensitivity = cycling_sensitivity(
        bins,
        circuit_model,
        float(
            selected[
                "small_unit_size_factor"
            ]
        ),
    )

    summary = pd.DataFrame([
        {
            "metric": "Selected small-unit size factor",
            "value": selected[
                "small_unit_size_factor"
            ],
            "unit": "fraction of current HERA",
        },
        {
            "metric": "Reference valid hours",
            "value": selected[
                "reference_valid_hours"
            ],
            "unit": "h",
        },
        {
            "metric": "Reference electricity",
            "value": selected[
                "reference_electricity_MWh"
            ],
            "unit": "MWh_el",
        },
        {
            "metric": "Mixed-fleet electricity",
            "value": selected[
                "mixed_electricity_MWh"
            ],
            "unit": "MWh_el",
        },
        {
            "metric": "Mixed-fleet electricity saving",
            "value": selected[
                "electrical_saving_MWh"
            ],
            "unit": "MWh_el",
        },
        {
            "metric": "Mixed-fleet electricity saving",
            "value": selected[
                "electrical_saving_percent"
            ],
            "unit": "%",
        },
        {
            "metric": "Heating cycling exposure reduction",
            "value": selected[
                "heating_cycling_reduction_hours"
            ],
            "unit": "h",
        },
        {
            "metric": "Cooling cycling exposure reduction",
            "value": selected[
                "cooling_cycling_reduction_hours"
            ],
            "unit": "h",
        },
        {
            "metric": "Peak-feasible vs reference",
            "value": bool(
                selected[
                    "peak_feasible"
                ]
            ),
            "unit": "",
        },
    ])

    export_table(
        sweep,
        OUTPUT_SIZE_SWEEP,
        "SizeSweep",
    )

    export_table(
        sensitivity,
        OUTPUT_CYCLING_SENSITIVITY,
        "CdSensitivity",
    )

    export_table(
        summary,
        OUTPUT_SUMMARY,
        "Summary",
    )

    pass


if __name__ == "__main__":
    main()
