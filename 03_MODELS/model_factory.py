"""
model_factory.py

Small reusable construction helper for the V2 HERA model.

Executable scripts still define their actual input file paths at the top.
This helper only avoids duplicating calibration/fallback construction logic.
"""

# ============================================================
# 1. IMPORTS
# ============================================================

from pathlib import Path


# ============================================================
# 2. CALIBRATION LOADING
# ============================================================

def load_calibrations(
    calibration_file: Path,
    table_io,
    hera_module,
    fallback_calibration: dict,
):
    calibration_file = Path(calibration_file)

    try:
        data = table_io.read_table(calibration_file)
    except FileNotFoundError:
        data = None

    if data is not None:
        calibrations = {}

        for _, row in data.iterrows():
            mode = str(row["mode"]).strip().lower()
            calibrations[mode] = hera_module.ModeCalibration(
                mode=mode,
                source=str(row.get("source", Path(calibration_file).name)),
                air_UA_100_kW_K=float(row["air_UA_100_kW_K"]),
                water_UA_ref_kW_K=float(row["water_UA_ref_kW_K"]),
                reference_air_approach_K=float(row["reference_air_approach_K"]),
                reference_water_approach_K=float(row["reference_water_approach_K"]),
                reference_fan_speed_fraction=float(row["reference_fan_speed_fraction"]),
            )

        if {"heating", "cooling"}.issubset(calibrations):
            return calibrations

    calibrations = {}

    for mode, values in fallback_calibration.items():
        calibrations[mode] = hera_module.ModeCalibration(
            mode=mode,
            source="fallback from previously validated analytical model",
            air_UA_100_kW_K=float(values["air_UA_100_kW_K"]),
            water_UA_ref_kW_K=float(values["water_UA_kW_K"]),
            reference_air_approach_K=float(values["reference_air_approach_K"]),
            reference_water_approach_K=float(values["reference_water_approach_K"]),
            reference_fan_speed_fraction=float(values["reference_fan_speed_fraction"]),
        )

    return calibrations


# ============================================================
# 3. CIRCUIT MODEL CONSTRUCTION
# ============================================================

def build_circuit_model(
    *,
    frascold_database: Path,
    calibration_file: Path,
    config,
    table_io,
    frascold_grid_module,
    hera_module,
    air_ht_exponent_override=None,
    water_ht_exponent_override=None,
):
    fmap = frascold_grid_module.FrascoldGridLookup(
        frascold_database
    )

    calibrations = load_calibrations(
        calibration_file,
        table_io,
        hera_module,
        config.HERA_FALLBACK_CALIBRATION,
    )

    model = hera_module.CircuitModel(
        fmap,
        calibrations,
        fan_rated_unit_kW=config.FAN_RATED_POWER_UNIT_KW,
        air_ht_exponent=(
            config.AIR_HT_EXPONENT
            if air_ht_exponent_override is None
            else float(air_ht_exponent_override)
        ),
        water_ht_exponent=(
            config.WATER_HT_EXPONENT
            if water_ht_exponent_override is None
            else float(water_ht_exponent_override)
        ),
        max_fan_multiplier=config.MAX_FAN_DESIGN_MULTIPLIER,
    )

    return model, calibrations
