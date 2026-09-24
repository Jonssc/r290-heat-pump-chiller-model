"""
16_hybrid_water_water_heat_recovery.py

Dedicated additional R290 water/water heat-recovery concept screening.

The V2 analysis preserves the previous validated screening method:
- February...July 2026 measured hybrid periods only;
- 5 kW heating/cooling load bins;
- 1 K outdoor/heating-water/cooling-water bins;
- actual measured RT403 and RT404 water temperatures;
- existing 3-HERA air/water reference;
- dedicated water/water unit with 1 or 2 R290 circuits;
- all 30...70 Hz points in 2.5 Hz steps;
- water/water duty fraction limited by BOTH simultaneous heating and cooling;
- residual air/water demand rounded to 2.5 kW;
- lowest total electrical power retained;
- no external water pumps.

This remains a concept model, not a product-specific water/water manufacturer
prediction.

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

HEAT_RECOVERY_MODEL_FILE = (
    PROJECT_ROOT
    / "03_MODELS"
    / "heat_recovery_model.py"
)

INPUT_HYBRID_POINTS = (
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

OUTPUT_ROWS = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "optimization"
    / "heat_recovery"
    / "hybrid_water_water_rows"
)

OUTPUT_SUMMARY = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "optimization"
    / "heat_recovery"
    / "hybrid_water_water_summary"
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
    "config_heat_recovery_v2",
    CONFIG_FILE,
)

table_io = load_module(
    "table_io_heat_recovery_v2",
    TABLE_IO_FILE,
)

grid_module = load_module(
    "grid_heat_recovery_v2",
    FRASCOLD_GRID_MODEL_FILE,
)

hera_module = load_module(
    "hera_heat_recovery_v2",
    HERA_MODEL_FILE,
)

factory = load_module(
    "factory_heat_recovery_v2",
    MODEL_FACTORY_FILE,
)

annual_model = load_module(
    "annual_heat_recovery_v2",
    ANNUAL_PLANT_MODEL_FILE,
)

heat_recovery = load_module(
    "heat_recovery_model_v2",
    HEAT_RECOVERY_MODEL_FILE,
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
# 5. MEASURED HYBRID BINNING
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


def prepare_hybrid_bins():
    if not INPUT_HYBRID_POINTS.exists():
        raise FileNotFoundError(
            "Run 14_hybrid_operation.py first."
        )

    data = table_io.read_table(
        INPUT_HYBRID_POINTS
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
        & data["Operating_state"].astype(str).eq(
            "Hybrid"
        )
    ].copy()

    data = data.dropna(
        subset=[
            "Heating_load_filtered_kW",
            "Cooling_load_filtered_kW",
            "Outdoor_C",
            "RT403_C",
            "RT404_C",
        ]
    )

    data[
        "heating_load_bin_kW"
    ] = round_to_step(
        data[
            "Heating_load_filtered_kW"
        ],
        config.HEAT_RECOVERY_LOAD_BIN_KW,
    )

    data[
        "cooling_load_bin_kW"
    ] = round_to_step(
        data[
            "Cooling_load_filtered_kW"
        ],
        config.HEAT_RECOVERY_LOAD_BIN_KW,
    )

    data[
        "outdoor_bin_C"
    ] = round_to_step(
        data[
            "Outdoor_C"
        ],
        config.HEAT_RECOVERY_TEMPERATURE_BIN_K,
    )

    data[
        "heating_water_bin_C"
    ] = round_to_step(
        data[
            "RT403_C"
        ],
        config.HEAT_RECOVERY_TEMPERATURE_BIN_K,
    )

    data[
        "cooling_water_bin_C"
    ] = round_to_step(
        data[
            "RT404_C"
        ],
        config.HEAT_RECOVERY_TEMPERATURE_BIN_K,
    )

    data["month"] = (
        data["timestamp"]
        .dt.to_period(
            "M"
        )
        .astype(str)
    )

    grouped = (
        data
        .groupby(
            [
                "month",
                "heating_load_bin_kW",
                "cooling_load_bin_kW",
                "outdoor_bin_C",
                "heating_water_bin_C",
                "cooling_water_bin_C",
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
# 6. SCREENING CALCULATION
# ============================================================

def run_screening(
    bins,
    circuit_model,
    calibrations,
):
    rows = []

    for point in bins.itertuples(
        index=False
    ):
        q_heat = float(
            point.heating_load_bin_kW
        )

        q_cool = float(
            point.cooling_load_bin_kW
        )

        outdoor_C = float(
            point.outdoor_bin_C
        )

        heating_water_C = float(
            point.heating_water_bin_C
        )

        cooling_water_C = float(
            point.cooling_water_bin_C
        )

        represented_hours = float(
            point.represented_hours
        )

        for UA_multiplier in [config.HEAT_RECOVERY_UA_MULTIPLIER]:
            result = (
                heat_recovery.best_heat_recovery_operation(
                    frascold_lookup=
                        circuit_model.fmap,
                    annual_plant_module=
                        annual_model,
                    circuit_model=
                        circuit_model,
                    heating_load_kW=
                        q_heat,
                    cooling_load_kW=
                        q_cool,
                    outdoor_C=
                        outdoor_C,
                    heating_water_out_C=
                        heating_water_C,
                    cooling_water_out_C=
                        cooling_water_C,
                    evaporator_UA_kW_K=(
                        calibrations[
                            "cooling"
                        ].water_UA_ref_kW_K
                        * float(
                            UA_multiplier
                        )
                    ),
                    condenser_UA_kW_K=(
                        calibrations[
                            "heating"
                        ].water_UA_ref_kW_K
                        * float(
                            UA_multiplier
                        )
                    ),
                    reference_cooling_water_approach_K=(
                        calibrations[
                            "cooling"
                        ].reference_water_approach_K
                    ),
                    reference_heating_water_approach_K=(
                        calibrations[
                            "heating"
                        ].reference_water_approach_K
                    ),
                    existing_fleet_tuple=(
                        1.0,
                        1.0,
                        1.0,
                    ),
                    maximum_water_water_circuits=(
                        config.HEAT_RECOVERY_MAX_CIRCUITS
                    ),
                    frequency_step_Hz=(
                        config.HEAT_RECOVERY_FREQUENCY_STEP_HZ
                    ),
                    residual_load_bin_kW=(
                        config.HEAT_RECOVERY_RESIDUAL_LOAD_BIN_KW
                    ),
                )
            )

            record = {
                "month": point.month,
                "heating_load_kW": q_heat,
                "cooling_load_kW": q_cool,
                "outdoor_C": outdoor_C,
                "heating_water_C": heating_water_C,
                "cooling_water_C": cooling_water_C,
                "represented_hours": represented_hours,
                "water_water_UA_multiplier":
                    float(
                        UA_multiplier
                    ),
                **result,
            }

            rows.append(
                record
            )

    return pd.DataFrame(
        rows
    )


# ============================================================
# 7. SUMMARY TABLES
# ============================================================

def summarize(
    results,
):
    valid = results[
        results[
            "model_status"
        ].astype(str).eq(
            "OK"
        )
    ].copy()

    rows = []

    for multiplier, group in valid.groupby(
        "water_water_UA_multiplier"
    ):
        represented_hours = float(
            group[
                "represented_hours"
            ].sum()
        )

        reference_MWh = float(
            (
                group[
                    "reference_air_water_power_kW"
                ]
                * group[
                    "represented_hours"
                ]
            ).sum()
            / 1000.0
        )

        recovery_MWh = float(
            (
                group[
                    "total_power_kW"
                ]
                * group[
                    "represented_hours"
                ]
            ).sum()
            / 1000.0
        )

        recovered_cooling_MWh = float(
            (
                group[
                    "recovered_cooling_kW"
                ]
                * group[
                    "represented_hours"
                ]
            ).sum()
            / 1000.0
        )

        recovered_heating_MWh = float(
            (
                group[
                    "recovered_heating_kW"
                ]
                * group[
                    "represented_hours"
                ]
            ).sum()
            / 1000.0
        )

        saving_MWh = (
            reference_MWh
            - recovery_MWh
        )

        rows.append({
            "water_water_UA_multiplier":
                multiplier,
            "modeled_hours":
                represented_hours,
            "reference_electricity_MWh":
                reference_MWh,
            "heat_recovery_electricity_MWh":
                recovery_MWh,
            "electricity_saving_MWh":
                saving_MWh,
            "electricity_saving_percent": (
                100.0
                * saving_MWh
                / reference_MWh
                if reference_MWh > 0
                else np.nan
            ),
            "recovered_cooling_MWh":
                recovered_cooling_MWh,
            "recovered_heating_MWh":
                recovered_heating_MWh,
        })

    return pd.DataFrame(
        rows
    )


# ============================================================
# 8. EXPORT
# ============================================================

def export_table(
    dataframe,
    output,
    sheet_name,
    *,
    full_rows=False,
):
    table_io.write_table(
        dataframe,
        output,
        export_csv=True,
        export_xlsx=(
            False
            if full_rows
            else config.EXPORT_XLSX
        ),
        csv_separator=config.CSV_SEPARATOR,
        csv_decimal=config.CSV_DECIMAL,
        float_format=config.CSV_FLOAT_FORMAT,
        sheet_name=sheet_name,
    )


# ============================================================
# 9. MAIN
# ============================================================

def main():
    bins = prepare_hybrid_bins()

    circuit_model, calibrations = (
        build_model()
    )

    results = run_screening(
        bins,
        circuit_model,
        calibrations,
    )

    cases = summarize(
        results
    )

    main_case = cases[
        np.isclose(
            cases[
                "water_water_UA_multiplier"
            ],
            1.0,
        )
    ]

    if main_case.empty:
        main_case = cases.iloc[
            [
                (
                    cases[
                        "water_water_UA_multiplier"
                    ]
                    - 1.0
                )
                .abs()
                .idxmin()
            ]
        ]

    row = main_case.iloc[0]

    summary = pd.DataFrame([
        {
            "metric":
                "Modeled simultaneous-operation hours",
            "value":
                row[
                    "modeled_hours"
                ],
            "unit":
                "h",
        },
        {
            "metric":
                "Existing air/water reference electricity",
            "value":
                row[
                    "reference_electricity_MWh"
                ],
            "unit":
                "MWh_el",
        },
        {
            "metric":
                "Dedicated water/water heat-recovery electricity",
            "value":
                row[
                    "heat_recovery_electricity_MWh"
                ],
            "unit":
                "MWh_el",
        },
        {
            "metric":
                "Hybrid-period electricity saving",
            "value":
                row[
                    "electricity_saving_MWh"
                ],
            "unit":
                "MWh_el",
        },
        {
            "metric":
                "Hybrid-period electricity saving",
            "value":
                row[
                    "electricity_saving_percent"
                ],
            "unit":
                "%",
        },
        {
            "metric":
                "Recovered cooling thermal energy",
            "value":
                row[
                    "recovered_cooling_MWh"
                ],
            "unit":
                "MWh_th",
        },
        {
            "metric":
                "Recovered heating thermal energy",
            "value":
                row[
                    "recovered_heating_MWh"
                ],
            "unit":
                "MWh_th",
        },
    ])

    export_table(
        results,
        OUTPUT_ROWS,
        "Rows",
        full_rows=True,
    )


    export_table(
        summary,
        OUTPUT_SUMMARY,
        "Summary",
    )

    pass


if __name__ == "__main__":
    main()
