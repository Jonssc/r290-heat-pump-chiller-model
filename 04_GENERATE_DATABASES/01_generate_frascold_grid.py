"""
01_generate_frascold_grid.py

Generates a reusable master compressor database.

KEY PRINCIPLE
-------------
The compressor model is calculated here once.
Plot scripts later read the generated CSV and do not recalculate the model.

To change the source workbook or output file later, edit the file paths in
Section 2 at the top of this file.
"""

# ============================================================
# 1. IMPORTS
# ============================================================

from pathlib import Path
import sys

import numpy as np
import pandas as pd


# ============================================================
# 2. FILES USED BY THIS SCRIPT
#    CHANGE THESE PATHS HERE IF A DIFFERENT FILE IS USED
# ============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

CONFIG_FILE = (
    PROJECT_ROOT
    / "00_CONFIG"
    / "config.py"
)

FRASCOLD_MODEL_FILE = (
    PROJECT_ROOT
    / "03_MODELS"
    / "frascold_model.py"
)

FRASCOLD_WORKBOOK = (
    PROJECT_ROOT
    / "01_RAW_DATA"
    / "Frascold"
    / "Frascold_R290_V30-84AXHT.xlsx"
)

OUTPUT_DATABASE_CSV = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "databases"
    / "frascold_performance_grid.csv"
)

OUTPUT_METADATA_CSV = (
    PROJECT_ROOT
    / "06_RESULTS"
    / "databases"
    / "frascold_performance_grid_metadata.csv"
)


# ============================================================
# 3. IMPORT PROJECT MODULES
# ============================================================

sys.path.insert(
    0,
    str(
        PROJECT_ROOT
    ),
)

from importlib.util import (
    module_from_spec,
    spec_from_file_location,
)


def load_module(
    module_name,
    file_path,
):
    spec = spec_from_file_location(
        module_name,
        file_path,
    )

    module = module_from_spec(
        spec
    )

    # Register before execution so dataclasses and other module-level
    # machinery can resolve the module namespace correctly.
    sys.modules[
        module_name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


config = load_module(
    "thesis_config",
    CONFIG_FILE,
)

frascold_module = load_module(
    "frascold_model",
    FRASCOLD_MODEL_FILE,
)

FrascoldMap = (
    frascold_module.FrascoldMap
)


# ============================================================
# 4. CHANGEABLE GRID SETTINGS
#    DEFAULTS COME FROM config.py
# ============================================================

EVAP_TEMP_MIN_C = (
    config.FRASCOLD_EVAP_TEMP_MIN_C
)

EVAP_TEMP_MAX_C = (
    config.FRASCOLD_EVAP_TEMP_MAX_C
)

EVAP_TEMP_STEP_K = (
    config.FRASCOLD_EVAP_TEMP_STEP_K
)

COND_TEMP_MIN_C = (
    config.FRASCOLD_COND_TEMP_MIN_C
)

COND_TEMP_MAX_C = (
    config.FRASCOLD_COND_TEMP_MAX_C
)

COND_TEMP_STEP_K = (
    config.FRASCOLD_COND_TEMP_STEP_K
)

FREQUENCY_MIN_HZ = (
    config.FRASCOLD_FREQUENCY_MIN_HZ
)

FREQUENCY_MAX_HZ = (
    config.FRASCOLD_FREQUENCY_MAX_HZ
)

FREQUENCY_STEP_HZ = (
    config.FRASCOLD_FREQUENCY_STEP_HZ
)

KEEP_INVALID_GRID_POINTS = (
    config.KEEP_INVALID_GRID_POINTS
)


# ============================================================
# 5. GRID CREATION HELPERS
# ============================================================

def inclusive_range(
    start,
    stop,
    step,
):
    count = int(
        round(
            (stop - start)
            / step
        )
    )

    return np.array(
        [
            start
            + index
            * step
            for index in range(
                count + 1
            )
        ],
        dtype=float,
    )


def classify_error(
    error,
):
    message = str(
        error
    )

    if (
        "INVALID_FRASCOLD_CELL"
        in message
    ):
        return (
            "INVALID_MAP_CELL"
        )

    if (
        "outside"
        in message.lower()
    ):
        return (
            "OUTSIDE_MAP_RANGE"
        )

    return (
        "MODEL_ERROR"
    )


# ============================================================
# 6. CALCULATE COMPLETE FRASCOLD GRID
# ============================================================

def generate_grid():
    model = FrascoldMap(
        FRASCOLD_WORKBOOK
    )

    evaporating_temperatures = (
        inclusive_range(
            EVAP_TEMP_MIN_C,
            EVAP_TEMP_MAX_C,
            EVAP_TEMP_STEP_K,
        )
    )

    condensing_temperatures = (
        inclusive_range(
            COND_TEMP_MIN_C,
            COND_TEMP_MAX_C,
            COND_TEMP_STEP_K,
        )
    )

    frequencies = (
        inclusive_range(
            FREQUENCY_MIN_HZ,
            FREQUENCY_MAX_HZ,
            FREQUENCY_STEP_HZ,
        )
    )

    rows = []

    for T_evap_C in (
        evaporating_temperatures
    ):
        for T_cond_C in (
            condensing_temperatures
        ):
            for frequency_Hz in (
                frequencies
            ):
                base_row = {
                    "T_evap_C":
                        float(
                            T_evap_C
                        ),

                    "T_cond_C":
                        float(
                            T_cond_C
                        ),

                    "temperature_lift_K":
                        float(
                            T_cond_C
                            - T_evap_C
                        ),

                    "frequency_Hz":
                        float(
                            frequency_Hz
                        ),
                }

                try:
                    result = (
                        model.interpolate(
                            T_evap_C,
                            T_cond_C,
                            frequency_Hz,
                        )
                    )

                    row = {
                        **base_row,

                        "model_status":
                            "OK",

                        "error_type":
                            "",

                        "evaporator_capacity_kW":
                            result[
                                "evaporator_capacity_kW"
                            ],

                        "condenser_capacity_kW":
                            result[
                                "condenser_capacity_kW"
                            ],

                        "compressor_power_kW":
                            result[
                                "compressor_power_kW"
                            ],

                        "cooling_EER":
                            result[
                                "cooling_EER"
                            ],

                        "heating_COP":
                            result[
                                "heating_COP"
                            ],

                        "current_A":
                            result[
                                "current_A"
                            ],

                        "mass_flow_kg_h":
                            result[
                                "mass_flow_kg_h"
                            ],

                        "discharge_temperature_C":
                            result[
                                "discharge_temperature_C"
                            ],
                    }

                    rows.append(
                        row
                    )

                except Exception as error:
                    if (
                        not KEEP_INVALID_GRID_POINTS
                    ):
                        continue

                    row = {
                        **base_row,

                        "model_status":
                            "INVALID",

                        "error_type":
                            classify_error(
                                error
                            ),

                        "evaporator_capacity_kW":
                            np.nan,

                        "condenser_capacity_kW":
                            np.nan,

                        "compressor_power_kW":
                            np.nan,

                        "cooling_EER":
                            np.nan,

                        "heating_COP":
                            np.nan,

                        "current_A":
                            np.nan,

                        "mass_flow_kg_h":
                            np.nan,

                        "discharge_temperature_C":
                            np.nan,
                    }

                    rows.append(
                        row
                    )

    dataframe = pd.DataFrame(
        rows
    )

    return (
        dataframe,
        model,
    )


# ============================================================
# 7. EXPORT MASTER DATABASE
# ============================================================

def export_database(
    dataframe,
    model,
):
    OUTPUT_DATABASE_CSV.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe.to_csv(
        OUTPUT_DATABASE_CSV,
        index=config.SAVE_CSV_INDEX,
        float_format=config.CSV_FLOAT_FORMAT,
    )

    valid = (
        dataframe[
            "model_status"
        ]
        == "OK"
    )

    metadata_rows = [
        {
            "item":
                "Model version",

            "value":
                config.MODEL_VERSION,

            "unit":
                "",
        },
        {
            "item":
                "Compressor",

            "value":
                config.COMPRESSOR_MODEL,

            "unit":
                "",
        },
        {
            "item":
                "Refrigerant",

            "value":
                config.REFRIGERANT,

            "unit":
                "",
        },
        {
            "item":
                "Source workbook",

            "value":
                FRASCOLD_WORKBOOK.name,

            "unit":
                "",
        },
        {
            "item":
                "Requested grid rows",

            "value":
                len(
                    dataframe
                ),

            "unit":
                "rows",
        },
        {
            "item":
                "Valid grid rows",

            "value":
                int(
                    valid.sum()
                ),

            "unit":
                "rows",
        },
        {
            "item":
                "Invalid grid rows",

            "value":
                int(
                    (
                        ~valid
                    ).sum()
                ),

            "unit":
                "rows",
        },
        {
            "item":
                "Evaporating temperature minimum",

            "value":
                EVAP_TEMP_MIN_C,

            "unit":
                "°C",
        },
        {
            "item":
                "Evaporating temperature maximum",

            "value":
                EVAP_TEMP_MAX_C,

            "unit":
                "°C",
        },
        {
            "item":
                "Evaporating temperature step",

            "value":
                EVAP_TEMP_STEP_K,

            "unit":
                "K",
        },
        {
            "item":
                "Condensing temperature minimum",

            "value":
                COND_TEMP_MIN_C,

            "unit":
                "°C",
        },
        {
            "item":
                "Condensing temperature maximum",

            "value":
                COND_TEMP_MAX_C,

            "unit":
                "°C",
        },
        {
            "item":
                "Condensing temperature step",

            "value":
                COND_TEMP_STEP_K,

            "unit":
                "K",
        },
        {
            "item":
                "Frequency minimum",

            "value":
                FREQUENCY_MIN_HZ,

            "unit":
                "Hz",
        },
        {
            "item":
                "Frequency maximum",

            "value":
                FREQUENCY_MAX_HZ,

            "unit":
                "Hz",
        },
        {
            "item":
                "Frequency step",

            "value":
                FREQUENCY_STEP_HZ,

            "unit":
                "Hz",
        },
        {
            "item":
                "Workbook evaporating map minimum",

            "value":
                model.tevaps.min(),

            "unit":
                "°C",
        },
        {
            "item":
                "Workbook evaporating map maximum",

            "value":
                model.tevaps.max(),

            "unit":
                "°C",
        },
        {
            "item":
                "Workbook condensing map minimum",

            "value":
                model.tconds.min(),

            "unit":
                "°C",
        },
        {
            "item":
                "Workbook condensing map maximum",

            "value":
                model.tconds.max(),

            "unit":
                "°C",
        },
        {
            "item":
                "Workbook frequency minimum",

            "value":
                model.frequencies.min(),

            "unit":
                "Hz",
        },
        {
            "item":
                "Workbook frequency maximum",

            "value":
                model.frequencies.max(),

            "unit":
                "Hz",
        },
        {
            "item":
                "Extrapolation",

            "value":
                "Disabled",

            "unit":
                "",
        },
    ]

    metadata = pd.DataFrame(
        metadata_rows
    )

    metadata.to_csv(
        OUTPUT_METADATA_CSV,
        index=False,
    )


# ============================================================
# 8. MAIN
# ============================================================

def main():
    pass
    pass

    pass

    pass

    dataframe, model = (
        generate_grid()
    )

    export_database(
        dataframe,
        model,
    )

    valid_rows = int(
        (
            dataframe[
                "model_status"
            ]
            == "OK"
        ).sum()
    )

    invalid_rows = (
        len(
            dataframe
        )
        - valid_rows
    )

    pass
    pass

    pass

    pass

    pass
    pass


if __name__ == "__main__":
    main()
