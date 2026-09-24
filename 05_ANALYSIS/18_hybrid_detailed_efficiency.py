"""
18_hybrid_detailed_efficiency.py

PHYSICALLY CONSISTENT HYBRID ANALYSIS

This file REPLACES the previous Hotfix-5 hybrid load/load contour analysis.

Core boundary
-------------
Every simultaneous heating/cooling calculation uses ONE common outdoor
temperature for all three HERA units:

    T_ambient,heating = T_ambient,cooling = measured RT090 outdoor temperature

Fixed required leaving-water temperatures:

    heating water out = 50 °C
    cooling water out = 7 °C

The model uses the ACTUAL measured hybrid timestamps and their simultaneous
building loads:
    Q_heating(t)
    Q_cooling(t)
    T_ambient(t)

The existing annual_plant_model.fleet_dispatch() is reused. That function
already enforces the physical three-HERA constraint:
- each HERA is OFF, HEATING, or COOLING;
- each HERA has 1 or 2 active refrigerant circuits;
- one HERA cannot heat and cool simultaneously;
- the total fleet contains exactly three identical HERA units.

Main outputs
------------
1. 5-minute measured-hybrid model results
2. 1 °C outdoor-temperature summary
3. overall hybrid-period energy-weighted summary
4. methodology / boundary table

The previous Hotfix-5 result and figure folders are deleted at the start so
stale load/load contour PNGs cannot remain beside the corrected results.

Important interpretation
------------------------
The plant model optimizes EFFECTIVE active circuit counts. It does not know
which physical cabinet is lead/lag at a timestamp. Canonical HERA slot columns
are therefore minimum-unit model allocations, not observed HP1/HP2/HP3 IDs.

HX "Delta T" columns produced here are refrigerant-to-fluid APPROACH
temperatures from the calibrated model. They are NOT a fixed hydronic
water-in/water-out Delta T. No fixed return-water temperature is imposed.
"""

# ============================================================
# 1. IMPORTS
# ============================================================

from pathlib import Path
from functools import lru_cache
import importlib.util
import shutil
import sys

import numpy as np
import pandas as pd


# ============================================================
# 2. FILES USED BY THIS SCRIPT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONFIG_FILE = PROJECT_ROOT / "00_CONFIG" / "config.py"
TABLE_IO_FILE = PROJECT_ROOT / "00_CONFIG" / "table_io.py"

ANNUAL_PLANT_MODEL_FILE = (
    PROJECT_ROOT / "03_MODELS" / "annual_plant_model.py"
)

FRASCOLD_GRID_MODEL_FILE = (
    PROJECT_ROOT / "03_MODELS" / "frascold_grid_model.py"
)

HERA_MODEL_FILE = (
    PROJECT_ROOT / "03_MODELS" / "hera_model.py"
)

MODEL_FACTORY_FILE = (
    PROJECT_ROOT / "03_MODELS" / "model_factory.py"
)

INPUT_HYBRID_CLASSIFIED = (
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

OUTPUT_FOLDER = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "annual"
    / "hybrid_detailed"
)

LEGACY_FIGURE_FOLDER = (
    PROJECT_ROOT
    / "08_THESIS_EXPORT"
    / "figures"
    / "annual"
    / "hybrid_detailed"
)


# ============================================================
# 3. USER-CHANGEABLE ANALYSIS SETTINGS
# ============================================================

# Measured simultaneous-load classification created by 14_hybrid_operation.py.
HYBRID_STATE_NAME = "Hybrid"

# Same model-resolution concept already used by the annual plant simulation.
OUTDOOR_MODEL_BIN_C = 1.0
LOAD_MODEL_BIN_KW = 2.5

# Water-temperature requirements.
HEATING_WATER_OUT_C = 50.0
COOLING_WATER_OUT_C = 7.0

# Use the same cycling treatment as the annual plant model.
CYCLING_DEGRADATION_COEFFICIENT = 0.15

# Frascold VFD interpolation resolution.
FREQUENCY_STEP_HZ = 2.5

# 1 °C summary bins require enough 5-minute points for a robust plotted result.
MIN_SUMMARY_SAMPLES_PER_OUTDOOR_BIN = 12

# Treat any residual model shortfall above this as capacity-limited.
MAX_SHORTFALL_FOR_FULLY_SERVED_KW = 0.10


# ============================================================
# 4. MODULE LOADING
# ============================================================

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


config = load_module(
    "config_hybrid_same_ambient",
    CONFIG_FILE,
)

table_io = load_module(
    "table_io_hybrid_same_ambient",
    TABLE_IO_FILE,
)

annual_plant = load_module(
    "annual_plant_hybrid_same_ambient",
    ANNUAL_PLANT_MODEL_FILE,
)

frascold_grid = load_module(
    "frascold_grid_hybrid_same_ambient",
    FRASCOLD_GRID_MODEL_FILE,
)

hera = load_module(
    "hera_hybrid_same_ambient",
    HERA_MODEL_FILE,
)

factory = load_module(
    "factory_hybrid_same_ambient",
    MODEL_FACTORY_FILE,
)


# ============================================================
# 5. GENERAL HELPERS
# ============================================================

def export_table(dataframe, stem, sheet_name):
    OUTPUT_FOLDER.mkdir(
        parents=True,
        exist_ok=True,
    )

    table_io.write_table(
        dataframe,
        OUTPUT_FOLDER / stem,
        export_csv=config.EXPORT_CSV,
        export_xlsx=config.EXPORT_XLSX,
        csv_separator=config.CSV_SEPARATOR,
        csv_decimal=config.CSV_DECIMAL,
        float_format=config.CSV_FLOAT_FORMAT,
        sheet_name=sheet_name,
    )


def round_step(value, step):
    value = float(value)

    if not np.isfinite(value):
        return np.nan

    return (
        round(
            value
            / float(step)
        )
        * float(step)
    )


def build_model():
    return factory.build_circuit_model(
        frascold_database=INPUT_FRASCOLD_DATABASE,
        calibration_file=INPUT_HX_CALIBRATION,
        config=config,
        table_io=table_io,
        frascold_grid_module=frascold_grid,
        hera_module=hera,
        air_ht_exponent_override=config.ANNUAL_AIR_HT_EXPONENT,
    )


def canonical_slot_states(
    heating_circuits,
    cooling_circuits,
):
    """Minimum-unit canonical allocation for reporting only.

    Example:
        heating circuits = 3
        cooling circuits = 2

    becomes:
        HERA slot 1 = heating, 2 circuits
        HERA slot 2 = heating, 1 circuit
        HERA slot 3 = cooling, 2 circuits

    The model does not assert that these are the physical HP1/HP2/HP3 cabinets.
    """

    states = []

    def safe_nonnegative_int(value):
        try:
            value = float(value)
        except Exception:
            return 0

        if not np.isfinite(value):
            return 0

        return int(
            max(
                round(value),
                0,
            )
        )

    remaining_heating = safe_nonnegative_int(
        heating_circuits
    )

    remaining_cooling = safe_nonnegative_int(
        cooling_circuits
    )

    while remaining_heating > 0 and len(states) < 3:
        active = min(
            2,
            remaining_heating,
        )

        states.append(
            (
                "heating",
                active,
            )
        )

        remaining_heating -= active

    while remaining_cooling > 0 and len(states) < 3:
        active = min(
            2,
            remaining_cooling,
        )

        states.append(
            (
                "cooling",
                active,
            )
        )

        remaining_cooling -= active

    while len(states) < 3:
        states.append(
            (
                "off",
                0,
            )
        )

    return states[:3]


# ============================================================
# 6. HX APPROACH AT THE SELECTED HYBRID OPERATING POINT
# ============================================================

def selected_mode_approach(
    circuit_model,
    mode,
    outdoor_C,
    water_out_C,
    frequency_Hz,
):
    if (
        not np.isfinite(
            frequency_Hz
        )
        or float(
            frequency_Hz
        )
        <= 0
    ):
        return {}

    fan_speed = float(
        circuit_model.cal[
            mode
        ].reference_fan_speed_fraction
    )

    result = circuit_model.safe_evaluate(
        circuit_model.case_class(
            mode=mode,
            outdoor_C=float(
                outdoor_C
            ),
            water_out_C=float(
                water_out_C
            ),
            frequency_Hz=float(
                frequency_Hz
            ),
            fan_speed_fraction=fan_speed,
        )
    )

    if result.get(
        "model_status"
    ) != "OK":
        return {}

    return {
        f"{mode}_T_evap_C":
            float(
                result.get(
                    "T_evap_C",
                    np.nan,
                )
            ),
        f"{mode}_T_cond_C":
            float(
                result.get(
                    "T_cond_C",
                    np.nan,
                )
            ),
        f"{mode}_air_approach_K":
            float(
                result.get(
                    "air_approach_K",
                    np.nan,
                )
            ),
        f"{mode}_water_approach_K":
            float(
                result.get(
                    "water_approach_K",
                    np.nan,
                )
            ),
        f"{mode}_refrigerant_lift_K":
            float(
                result.get(
                    "temperature_lift_K",
                    np.nan,
                )
            ),
    }


# ============================================================
# 7. PHYSICALLY CONSISTENT SAME-AMBIENT DISPATCH
# ============================================================

def main():
    if not INPUT_HYBRID_CLASSIFIED.exists():
        raise FileNotFoundError(
            "Run 14_hybrid_operation.py first. Missing:\n"
            f"{INPUT_HYBRID_CLASSIFIED}"
        )

    if not INPUT_FRASCOLD_DATABASE.exists():
        raise FileNotFoundError(
            f"Missing Frascold database:\n{INPUT_FRASCOLD_DATABASE}"
        )

    # Remove every Hotfix-5 hybrid-detail result/figure before writing the new
    # physically consistent analysis. This prevents stale contour PNGs/tables.
    if OUTPUT_FOLDER.exists():
        shutil.rmtree(
            OUTPUT_FOLDER
        )

    if LEGACY_FIGURE_FOLDER.exists():
        shutil.rmtree(
            LEGACY_FIGURE_FOLDER
        )

    data = table_io.read_table(
        INPUT_HYBRID_CLASSIFIED
    )

    data[
        "timestamp"
    ] = pd.to_datetime(
        data[
            "timestamp"
        ],
        errors="coerce",
    )

    data = data[
        data[
            "Operating_state"
        ].astype(str).eq(
            HYBRID_STATE_NAME
        )
    ].copy()

    required_columns = [
        "timestamp",
        "Outdoor_C",
        "Heating_load_filtered_kW",
        "Cooling_load_filtered_kW",
    ]

    missing = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing:
        raise KeyError(
            "Missing required hybrid columns: "
            + ", ".join(
                missing
            )
        )

    for column in (
        "Outdoor_C",
        "Heating_load_filtered_kW",
        "Cooling_load_filtered_kW",
    ):
        data[
            column
        ] = pd.to_numeric(
            data[
                column
            ],
            errors="coerce",
        )

    data = data.dropna(
        subset=[
            "timestamp",
            "Outdoor_C",
            "Heating_load_filtered_kW",
            "Cooling_load_filtered_kW",
        ]
    ).copy()

    data = data[
        (
            data[
                "Heating_load_filtered_kW"
            ]
            > 0
        )
        & (
            data[
                "Cooling_load_filtered_kW"
            ]
            > 0
        )
    ].copy()

    if data.empty:
        raise RuntimeError(
            "No measured simultaneous heating/cooling rows remain."
        )

    data[
        "Outdoor_model_bin_C"
    ] = data[
        "Outdoor_C"
    ].apply(
        lambda value:
            round_step(
                value,
                OUTDOOR_MODEL_BIN_C,
            )
    )

    data[
        "Heating_model_bin_kW"
    ] = data[
        "Heating_load_filtered_kW"
    ].apply(
        lambda value:
            max(
                round_step(
                    value,
                    LOAD_MODEL_BIN_KW,
                ),
                0.0,
            )
    )

    data[
        "Cooling_model_bin_kW"
    ] = data[
        "Cooling_load_filtered_kW"
    ].apply(
        lambda value:
            max(
                round_step(
                    value,
                    LOAD_MODEL_BIN_KW,
                ),
                0.0,
            )
    )

    circuit_model, calibrations = build_model()

    @lru_cache(
        maxsize=None
    )
    def dispatch(
        outdoor_C,
        heating_load_kW,
        cooling_load_kW,
    ):
        result = annual_plant.fleet_dispatch(
            circuit_model,
            (
                1.0,
                1.0,
                1.0,
            ),
            float(
                heating_load_kW
            ),
            float(
                cooling_load_kW
            ),
            float(
                outdoor_C
            ),
            float(
                HEATING_WATER_OUT_C
            ),
            float(
                COOLING_WATER_OUT_C
            ),
            float(
                CYCLING_DEGRADATION_COEFFICIENT
            ),
            float(
                FREQUENCY_STEP_HZ
            ),
        )

        result = dict(
            result
        )

        result.update(
            selected_mode_approach(
                circuit_model,
                "heating",
                outdoor_C,
                HEATING_WATER_OUT_C,
                result.get(
                    "heating_frequency_Hz",
                    np.nan,
                ),
            )
        )

        result.update(
            selected_mode_approach(
                circuit_model,
                "cooling",
                outdoor_C,
                COOLING_WATER_OUT_C,
                result.get(
                    "cooling_frequency_Hz",
                    np.nan,
                ),
            )
        )

        return result

    unique_points = (
        data[
            [
                "Outdoor_model_bin_C",
                "Heating_model_bin_kW",
                "Cooling_model_bin_kW",
            ]
        ]
        .drop_duplicates()
        .reset_index(
            drop=True
        )
    )

    model_rows = []

    for row in unique_points.itertuples(
        index=False
    ):
        result = dispatch(
            float(
                row.Outdoor_model_bin_C
            ),
            float(
                row.Heating_model_bin_kW
            ),
            float(
                row.Cooling_model_bin_kW
            ),
        )

        result[
            "Outdoor_model_bin_C"
        ] = float(
            row.Outdoor_model_bin_C
        )

        result[
            "Heating_model_bin_kW"
        ] = float(
            row.Heating_model_bin_kW
        )

        result[
            "Cooling_model_bin_kW"
        ] = float(
            row.Cooling_model_bin_kW
        )

        model_rows.append(
            result
        )

    model_lookup = pd.DataFrame(
        model_rows
    )

    data = data.merge(
        model_lookup,
        on=[
            "Outdoor_model_bin_C",
            "Heating_model_bin_kW",
            "Cooling_model_bin_kW",
        ],
        how="left",
    )

    data[
        "fully_served"
    ] = (
        data[
            "model_status"
        ].astype(str).eq(
            "OK"
        )
        & (
            pd.to_numeric(
                data[
                    "total_shortfall_kW"
                ],
                errors="coerce",
            )
            <= MAX_SHORTFALL_FOR_FULLY_SERVED_KW
        )
    )

    data[
        "heating_COP"
    ] = np.where(
        pd.to_numeric(
            data[
                "heating_power_kW"
            ],
            errors="coerce",
        )
        > 0,
        pd.to_numeric(
            data[
                "heating_served_kW"
            ],
            errors="coerce",
        )
        / pd.to_numeric(
            data[
                "heating_power_kW"
            ],
            errors="coerce",
        ),
        np.nan,
    )

    data[
        "cooling_EER"
    ] = np.where(
        pd.to_numeric(
            data[
                "cooling_power_kW"
            ],
            errors="coerce",
        )
        > 0,
        pd.to_numeric(
            data[
                "cooling_served_kW"
            ],
            errors="coerce",
        )
        / pd.to_numeric(
            data[
                "cooling_power_kW"
            ],
            errors="coerce",
        ),
        np.nan,
    )

    data[
        "combined_heating_cooling_efficiency"
    ] = np.where(
        pd.to_numeric(
            data[
                "plant_power_kW"
            ],
            errors="coerce",
        )
        > 0,
        (
            pd.to_numeric(
                data[
                    "heating_served_kW"
                ],
                errors="coerce",
            )
            + pd.to_numeric(
                data[
                    "cooling_served_kW"
                ],
                errors="coerce",
            )
        )
        / pd.to_numeric(
            data[
                "plant_power_kW"
            ],
            errors="coerce",
        ),
        np.nan,
    )

    # Canonical model-slot information. This does not identify physical HP1/2/3.
    for index, row in data.iterrows():
        states = canonical_slot_states(
            row.get(
                "active_heating_circuits",
                0,
            ),
            row.get(
                "active_cooling_circuits",
                0,
            ),
        )

        for slot_number, (
            mode,
            circuits,
        ) in enumerate(
            states,
            start=1,
        ):
            prefix = (
                f"model_HERA_slot_{slot_number}"
            )

            data.at[
                index,
                f"{prefix}_mode"
            ] = mode

            data.at[
                index,
                f"{prefix}_active_circuits"
            ] = circuits

            if mode == "heating":
                scale = max(
                    int(
                        row.get(
                            "active_heating_circuits",
                            0,
                        )
                    ),
                    1,
                )

                per_circuit_load = (
                    float(
                        row.get(
                            "heating_served_kW",
                            0.0,
                        )
                    )
                    / scale
                )

                per_circuit_power = (
                    float(
                        row.get(
                            "heating_power_kW",
                            0.0,
                        )
                    )
                    / scale
                )

                frequency = row.get(
                    "heating_frequency_Hz",
                    np.nan,
                )

            elif mode == "cooling":
                scale = max(
                    int(
                        row.get(
                            "active_cooling_circuits",
                            0,
                        )
                    ),
                    1,
                )

                per_circuit_load = (
                    float(
                        row.get(
                            "cooling_served_kW",
                            0.0,
                        )
                    )
                    / scale
                )

                per_circuit_power = (
                    float(
                        row.get(
                            "cooling_power_kW",
                            0.0,
                        )
                    )
                    / scale
                )

                frequency = row.get(
                    "cooling_frequency_Hz",
                    np.nan,
                )

            else:
                per_circuit_load = 0.0
                per_circuit_power = 0.0
                frequency = 0.0

            data.at[
                index,
                f"{prefix}_frequency_Hz"
            ] = frequency

            data.at[
                index,
                f"{prefix}_useful_load_kW"
            ] = (
                circuits
                * per_circuit_load
            )

            data.at[
                index,
                f"{prefix}_electric_power_kW"
            ] = (
                circuits
                * per_circuit_power
            )

            data.at[
                index,
                f"{prefix}_COP_or_EER"
            ] = (
                (
                    per_circuit_load
                    / per_circuit_power
                )
                if (
                    circuits > 0
                    and per_circuit_power > 0
                )
                else np.nan
            )

    data[
        "model_unit_identity_note"
    ] = (
        "HERA slot 1/2/3 are canonical minimum-unit model allocations, "
        "not observed physical HP1/HP2/HP3 identities."
    )

    data[
        "water_temperature_boundary_note"
    ] = (
        "Heating leaving-water requirement = 50 C; cooling leaving-water "
        "requirement = 7 C. No fixed hydronic return temperature or water-side "
        "inlet/outlet Delta T is imposed."
    )

    # ========================================================
    # 8. 1 °C OUTDOOR-TEMPERATURE SUMMARY
    # ========================================================

    timestep_h = (
        float(
            config.SOURCE_TIMESTEP_MINUTES
        )
        / 60.0
    )

    valid = data[
        data[
            "model_status"
        ].astype(str).eq(
            "OK"
        )
    ].copy()

    summary_rows = []

    for outdoor_bin, group in data.groupby(
        "Outdoor_model_bin_C"
    ):
        if len(
            group
        ) < MIN_SUMMARY_SAMPLES_PER_OUTDOOR_BIN:
            continue

        modeled = group[
            group[
                "model_status"
            ].astype(str).eq(
                "OK"
            )
        ].copy()

        row = {
            "Outdoor_C":
                float(
                    outdoor_bin
                ),
            "sample_count":
                int(
                    len(
                        group
                    )
                ),
            "hybrid_hours":
                float(
                    len(
                        group
                    )
                    * timestep_h
                ),
            "model_valid_sample_count":
                int(
                    len(
                        modeled
                    )
                ),
            "model_valid_share_percent":
                (
                    100.0
                    * len(
                        modeled
                    )
                    / len(
                        group
                    )
                ),
            "measured_heating_load_mean_kW":
                float(
                    pd.to_numeric(
                        group[
                            "Heating_load_filtered_kW"
                        ],
                        errors="coerce",
                    ).mean()
                ),
            "measured_heating_load_median_kW":
                float(
                    pd.to_numeric(
                        group[
                            "Heating_load_filtered_kW"
                        ],
                        errors="coerce",
                    ).median()
                ),
            "measured_cooling_load_mean_kW":
                float(
                    pd.to_numeric(
                        group[
                            "Cooling_load_filtered_kW"
                        ],
                        errors="coerce",
                    ).mean()
                ),
            "measured_cooling_load_median_kW":
                float(
                    pd.to_numeric(
                        group[
                            "Cooling_load_filtered_kW"
                        ],
                        errors="coerce",
                    ).median()
                ),
        }

        if modeled.empty:
            summary_rows.append(
                row
            )
            continue

        heat_energy = (
            pd.to_numeric(
                modeled[
                    "heating_served_kW"
                ],
                errors="coerce",
            ).sum()
            * timestep_h
        )

        cool_energy = (
            pd.to_numeric(
                modeled[
                    "cooling_served_kW"
                ],
                errors="coerce",
            ).sum()
            * timestep_h
        )

        heating_electricity = (
            pd.to_numeric(
                modeled[
                    "heating_power_kW"
                ],
                errors="coerce",
            ).sum()
            * timestep_h
        )

        cooling_electricity = (
            pd.to_numeric(
                modeled[
                    "cooling_power_kW"
                ],
                errors="coerce",
            ).sum()
            * timestep_h
        )

        total_electricity = (
            heating_electricity
            + cooling_electricity
        )

        row.update({
            "heating_COP_energy_weighted":
                (
                    heat_energy
                    / heating_electricity
                    if heating_electricity > 0
                    else np.nan
                ),
            "cooling_EER_energy_weighted":
                (
                    cool_energy
                    / cooling_electricity
                    if cooling_electricity > 0
                    else np.nan
                ),
            "combined_efficiency_energy_weighted":
                (
                    (
                        heat_energy
                        + cool_energy
                    )
                    / total_electricity
                    if total_electricity > 0
                    else np.nan
                ),
            "mean_heating_power_kW":
                float(
                    pd.to_numeric(
                        modeled[
                            "heating_power_kW"
                        ],
                        errors="coerce",
                    ).mean()
                ),
            "mean_cooling_power_kW":
                float(
                    pd.to_numeric(
                        modeled[
                            "cooling_power_kW"
                        ],
                        errors="coerce",
                    ).mean()
                ),
            "mean_total_power_kW":
                float(
                    pd.to_numeric(
                        modeled[
                            "plant_power_kW"
                        ],
                        errors="coerce",
                    ).mean()
                ),
            "mean_active_heating_HERAs":
                float(
                    pd.to_numeric(
                        modeled[
                            "active_heating_units"
                        ],
                        errors="coerce",
                    ).mean()
                ),
            "mean_active_cooling_HERAs":
                float(
                    pd.to_numeric(
                        modeled[
                            "active_cooling_units"
                        ],
                        errors="coerce",
                    ).mean()
                ),
            "mean_active_HERAs_total":
                float(
                    pd.to_numeric(
                        modeled[
                            "active_units_total"
                        ],
                        errors="coerce",
                    ).mean()
                ),
            "mean_active_heating_circuits":
                float(
                    pd.to_numeric(
                        modeled[
                            "active_heating_circuits"
                        ],
                        errors="coerce",
                    ).mean()
                ),
            "mean_active_cooling_circuits":
                float(
                    pd.to_numeric(
                        modeled[
                            "active_cooling_circuits"
                        ],
                        errors="coerce",
                    ).mean()
                ),
            "mean_active_circuits_total":
                float(
                    pd.to_numeric(
                        modeled[
                            "active_circuits_total"
                        ],
                        errors="coerce",
                    ).mean()
                ),
            "mean_heating_frequency_Hz":
                float(
                    pd.to_numeric(
                        modeled[
                            "heating_frequency_Hz"
                        ],
                        errors="coerce",
                    ).replace(
                        0,
                        np.nan,
                    ).mean()
                ),
            "mean_cooling_frequency_Hz":
                float(
                    pd.to_numeric(
                        modeled[
                            "cooling_frequency_Hz"
                        ],
                        errors="coerce",
                    ).replace(
                        0,
                        np.nan,
                    ).mean()
                ),
            "mean_heating_air_approach_K":
                float(
                    pd.to_numeric(
                        modeled[
                            "heating_air_approach_K"
                        ],
                        errors="coerce",
                    ).mean()
                ),
            "mean_heating_water_approach_K":
                float(
                    pd.to_numeric(
                        modeled[
                            "heating_water_approach_K"
                        ],
                        errors="coerce",
                    ).mean()
                ),
            "mean_cooling_air_approach_K":
                float(
                    pd.to_numeric(
                        modeled[
                            "cooling_air_approach_K"
                        ],
                        errors="coerce",
                    ).mean()
                ),
            "mean_cooling_water_approach_K":
                float(
                    pd.to_numeric(
                        modeled[
                            "cooling_water_approach_K"
                        ],
                        errors="coerce",
                    ).mean()
                ),
        })

        summary_rows.append(
            row
        )

    outdoor_summary = pd.DataFrame(
        summary_rows
    ).sort_values(
        "Outdoor_C"
    )

    # ========================================================
    # 9. OVERALL HYBRID-PERIOD SUMMARY
    # ========================================================

    overall_rows = []

    if not valid.empty:
        heating_energy_kWh = (
            pd.to_numeric(
                valid[
                    "heating_served_kW"
                ],
                errors="coerce",
            ).sum()
            * timestep_h
        )

        cooling_energy_kWh = (
            pd.to_numeric(
                valid[
                    "cooling_served_kW"
                ],
                errors="coerce",
            ).sum()
            * timestep_h
        )

        heating_electricity_kWh = (
            pd.to_numeric(
                valid[
                    "heating_power_kW"
                ],
                errors="coerce",
            ).sum()
            * timestep_h
        )

        cooling_electricity_kWh = (
            pd.to_numeric(
                valid[
                    "cooling_power_kW"
                ],
                errors="coerce",
            ).sum()
            * timestep_h
        )

        total_electricity_kWh = (
            heating_electricity_kWh
            + cooling_electricity_kWh
        )

        overall_rows = [
            {
                "metric":
                    "Measured hybrid rows",
                "value":
                    len(
                        data
                    ),
                "unit":
                    "samples",
            },
            {
                "metric":
                    "Measured hybrid duration",
                "value":
                    len(
                        data
                    )
                    * timestep_h,
                "unit":
                    "h",
            },
            {
                "metric":
                    "Model-valid hybrid rows",
                "value":
                    len(
                        valid
                    ),
                "unit":
                    "samples",
            },
            {
                "metric":
                    "Model-valid share",
                "value":
                    100.0
                    * len(
                        valid
                    )
                    / len(
                        data
                    ),
                "unit":
                    "%",
            },
            {
                "metric":
                    "Heating energy served during model-valid hybrid periods",
                "value":
                    heating_energy_kWh
                    / 1000.0,
                "unit":
                    "MWh_th",
            },
            {
                "metric":
                    "Cooling energy served during model-valid hybrid periods",
                "value":
                    cooling_energy_kWh
                    / 1000.0,
                "unit":
                    "MWh_th",
            },
            {
                "metric":
                    "Modeled HERA electricity during model-valid hybrid periods",
                "value":
                    total_electricity_kWh
                    / 1000.0,
                "unit":
                    "MWh_el",
            },
            {
                "metric":
                    "Hybrid-period heating COP",
                "value":
                    (
                        heating_energy_kWh
                        / heating_electricity_kWh
                        if heating_electricity_kWh > 0
                        else np.nan
                    ),
                "unit":
                    "-",
            },
            {
                "metric":
                    "Hybrid-period cooling EER",
                "value":
                    (
                        cooling_energy_kWh
                        / cooling_electricity_kWh
                        if cooling_electricity_kWh > 0
                        else np.nan
                    ),
                "unit":
                    "-",
            },
            {
                "metric":
                    "Hybrid-period combined heating + cooling efficiency",
                "value":
                    (
                        (
                            heating_energy_kWh
                            + cooling_energy_kWh
                        )
                        / total_electricity_kWh
                        if total_electricity_kWh > 0
                        else np.nan
                    ),
                "unit":
                    "-",
            },
        ]

    overall_summary = pd.DataFrame(
        overall_rows
    )

    methodology = pd.DataFrame([
        {
            "item":
                "Outdoor temperature boundary",
            "value":
                "Same measured RT090 outdoor temperature is used for heating and cooling at every hybrid timestamp.",
        },
        {
            "item":
                "Heating water requirement",
            "value":
                "50 °C leaving-water temperature.",
        },
        {
            "item":
                "Cooling water requirement",
            "value":
                "7 °C leaving-water temperature.",
        },
        {
            "item":
                "Hydronic water Delta T",
            "value":
                "Not fixed. No return-water temperature is imposed in this analytical HERA model.",
        },
        {
            "item":
                "HX Delta T reported",
            "value":
                "Refrigerant-to-air and refrigerant-to-water approach temperature from Q/UA calibration.",
        },
        {
            "item":
                "Fleet constraint",
            "value":
                "Three HERA units; each unit may be off, heat, or cool; one or two active circuits per unit; no unit heats and cools simultaneously.",
        },
        {
            "item":
                "Electrical boundary",
            "value":
                "HERA compressor(s) + normal outdoor-coil fan power; external hydronic pumps excluded.",
        },
        {
            "item":
                "Cycling treatment",
            "value":
                f"Below-minimum-load cycling degradation coefficient Cd = {CYCLING_DEGRADATION_COEFFICIENT:.2f}.",
        },
        {
            "item":
                "Model binning",
            "value":
                f"Outdoor = {OUTDOOR_MODEL_BIN_C:.1f} K; heating/cooling load = {LOAD_MODEL_BIN_KW:.1f} kW. Actual timestamps are retained and mapped to the nearest model bin.",
        },
        {
            "item":
                "Unit identity",
            "value":
                "Canonical model HERA slots are not observed physical HP1/HP2/HP3 lead/lag identities.",
        },
    ])

    export_table(
        data,
        "hybrid_same_ambient_5min_results",
        "Hybrid5min",
    )

    export_table(
        outdoor_summary,
        "hybrid_same_ambient_outdoor_summary",
        "OutdoorSummary",
    )

    export_table(
        overall_summary,
        "hybrid_same_ambient_overall_summary",
        "OverallSummary",
    )

    export_table(
        methodology,
        "hybrid_same_ambient_methodology",
        "Methodology",
    )

    pass

    pass

    pass

    pass


if __name__ == "__main__":
    main()
