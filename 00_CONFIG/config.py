"""
config.py

Central changeable settings for the reorganized R290 thesis model.

RULES
-----
1. General numerical assumptions belong here.
2. Every executable script still repeats the FILES USED BY THIS SCRIPT section
   at the top so a later source-file replacement does not require code searching.
3. Plot selection belongs in each plot script, not in the models.
"""

# ============================================================
# 1. PROJECT IDENTIFICATION
# ============================================================

MODEL_VERSION = "1.0"
REFRIGERANT = "R290"
COMPRESSOR_MODEL = "Frascold V30-84AXHT"


# ============================================================
# 2. FRASCOLD MASTER GRID
# ============================================================

FRASCOLD_EVAP_TEMP_MIN_C = -30.0
FRASCOLD_EVAP_TEMP_MAX_C = 15.0
FRASCOLD_EVAP_TEMP_STEP_K = 1.0

FRASCOLD_COND_TEMP_MIN_C = 25.0
FRASCOLD_COND_TEMP_MAX_C = 65.0
FRASCOLD_COND_TEMP_STEP_K = 1.0

FRASCOLD_FREQUENCY_MIN_HZ = 30.0
FRASCOLD_FREQUENCY_MAX_HZ = 70.0
FRASCOLD_FREQUENCY_STEP_HZ = 2.5
KEEP_INVALID_GRID_POINTS = True


# ============================================================
# 3. GLYCOL / WATER DATABASE
# ============================================================

GLYCOL_CONCENTRATIONS_VOL_PERCENT = [
    0,
    20,
    25,
    30,
    35,
    40,
    45,
    50,
]

GLYCOL_TEMPERATURE_MIN_C = -20.0
GLYCOL_TEMPERATURE_MAX_C = 50.0
GLYCOL_TEMPERATURE_STEP_K = 5.0

# Internal reference concentration for relative hydraulic/HX screening.
GLYCOL_REFERENCE_CONCENTRATION_PERCENT = 40
WATER_SIDE_RESISTANCE_FRACTION = 0.50


# ============================================================
# 4. KIONA FILTER SETTINGS
# ============================================================

KIONA_STABLE_WINDOW_ROWS = 3
KIONA_MIN_STABLE_PERIOD_ROWS = 3
KIONA_MAX_TIMESTAMP_GAP_MIN = 7.5
KIONA_MIN_ELECTRICAL_POWER_KW = 2.0
KIONA_MIN_CAPACITY_REQUEST_PERCENT = 0.1

# Circuit activity is based on compressor runtime counters when available.
# If they cannot be used, pressure lift is the fallback. Known-bad fan-start
# signals are not used to classify circuit activity.
KIONA_PRESSURE_LIFT_ACTIVE_BAR = 5.0

KIONA_MAX_PEL_STD_KW = 1.5
KIONA_MAX_CAPACITY_REQUEST_STD_PERCENT = 5.0
KIONA_MAX_SETPOINT_STD_K = 0.30
KIONA_MAX_HOT_SIDE_TEMP_STD_K = 0.80
KIONA_MAX_OUTDOOR_STD_K = 1.00
KIONA_MAX_EVAP_PRESSURE_STD_BAR = 0.35
KIONA_MAX_COND_PRESSURE_STD_BAR = 0.50
KIONA_MAX_SUCTION_TEMP_STD_K = 2.00
KIONA_MAX_SUPERHEAT_STD_K = 2.00

ATMOSPHERIC_PRESSURE_BAR = 1.01325
HP1_MIN_EVAP_AIR_APPROACH_K = 1.0
HP1_MIN_COND_WATER_APPROACH_K = 1.0


# ============================================================
# 5. VALIDATION SETTINGS
# ============================================================

# Prefer a measured compressor-frequency column when one is present in future
# Kiona datasets. Otherwise the historical provisional capacity-request mapping
# is retained and explicitly labelled as an assumption.
VALIDATION_FREQUENCY_METHOD = "auto"  # auto | measured | provisional
VALIDATION_MIN_FREQUENCY_HZ = 30.0
VALIDATION_MAX_FREQUENCY_HZ = 70.0
VALIDATION_COMMAND_TO_HZ = 0.70

# Four normal outdoor-coil EC fans per HERA, total rated input 1.34 kW.
FAN_RATED_POWER_UNIT_KW = 1.34
FAN_RATED_POWER_PER_CIRCUIT_KW = FAN_RATED_POWER_UNIT_KW / 2.0

# No external hydronic pump is included in the chiller validation boundary.
VALIDATION_INCLUDE_EXTERNAL_PUMP = False

# When no reliable fan-speed measurement exists, this proxy is used only as a
# screening approximation and is written to every validation row.
VALIDATION_FAN_METHOD = "capacity_proxy"  # capacity_proxy | rated_per_active_circuit


# ============================================================
# 6. HERA MODEL / PLANT SETTINGS
# ============================================================

NUMBER_OF_HERA_UNITS = 3
HEATING_WATER_OUT_C = 50.0
COOLING_WATER_OUT_C = 7.0

FREQUENCY_MIN_HZ = 30.0
FREQUENCY_MAX_HZ = 70.0
FREQUENCY_STEP_HZ = 2.5

AIR_HT_EXPONENT = 0.60
WATER_HT_EXPONENT = 0.80
MAX_FAN_DESIGN_MULTIPLIER = 1.50
# Values above 1.00 are hypothetical fan-design / oversizing sensitivity,
# not a claim that the installed EC fans can physically run above rated speed.
# Fan electrical power follows the existing cubic-law screening relation.
CYCLING_DEGRADATION_COEFFICIENT = 0.15

# Field-calibrated fallback values from the existing validated analytical model.
# They are used only if the new calibration table has not yet been generated.
HERA_FALLBACK_CALIBRATION = {
    "heating": {
        "air_UA_100_kW_K": ,
        "water_UA_kW_K": ,
        "reference_air_approach_K": ,
        "reference_water_approach_K": ,
        "reference_fan_speed_fraction": ,
    },
    "cooling": {
        "air_UA_100_kW_K": ,
        "water_UA_kW_K": ,
        "reference_air_approach_K": ,
        "reference_water_approach_K": ,
        "reference_fan_speed_fraction": ,
    },
}

# ============================================================
# 7. ANNUAL SETTINGS
# ============================================================

ANNUAL_START_DATE = "2025-08-11"
ANNUAL_END_DATE_EXCLUSIVE = "2026-08-11"

# ============================================================
# 8. OUTPUT SETTINGS
# ============================================================

# CSV remains convenient for Python. Human-readable result tables can also be
# exported to true XLSX files, which guarantees one variable per Excel cell.
EXPORT_CSV = True
EXPORT_XLSX = False
CSV_SEPARATOR = ";"
CSV_DECIMAL = ","
CSV_FLOAT_FORMAT = "%.6f"
SAVE_CSV_INDEX = False
PLOT_DPI = 220


# ============================================================
# 9. PARAMETRIC / OPTIMISATION STUDY SETTINGS
# ============================================================

# Reference conditions used only to create standardized analytical study tables.
# These can be changed without modifying the model code.
ANALYTIC_REFERENCE_FREQUENCY_HZ = 50.0
ANALYTIC_HEATING_OUTDOOR_C = 7.0
ANALYTIC_COOLING_OUTDOOR_C = 35.0

HEATING_WATER_TEMP_STUDY_C = [
    35.0, 40.0, 45.0, 50.0, 55.0, 60.0
]

COOLING_WATER_TEMP_STUDY_C = [
    5.0, 6.0, 7.0, 8.0, 10.0, 12.0
]

HEATING_OUTDOOR_TEMP_STUDY_C = [
    -15.0, -10.0, -7.0, -5.0, 0.0, 2.0, 7.0, 12.0, 15.0
]

COOLING_OUTDOOR_TEMP_STUDY_C = [
    10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0
]

FOULING_UA_MULTIPLIERS = [
    0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00
]

AIR_UA_FINE_MULTIPLIERS = [
    0.70, 0.775, 0.85, 0.925, 1.00, 1.075, 1.15, 1.225,
    1.30, 1.375, 1.45, 1.525, 1.60
]

WATER_UA_FINE_MULTIPLIERS = [
    0.70, 0.775, 0.85, 0.925, 1.00, 1.075, 1.15, 1.225,
    1.30, 1.375, 1.45, 1.525, 1.60
]

FAN_FINE_FRACTIONS = [
    0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70,
    0.75, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05,
    1.10, 1.15, 1.20, 1.25, 1.30, 1.35, 1.40,
    1.45, 1.50
]

WATER_FLOW_FINE_FRACTIONS = [
    0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90,
    0.95, 1.00, 1.05, 1.10, 1.15, 1.20
]



# ============================================================
# 10. PUMP / HYDRAULIC SCREENING SETTINGS
# ============================================================

# Installed per-unit Grundfos MGE90LC family.
# P2 / PDS efficiency is a conservative full-load electrical reference;
# it is NOT measured absorbed pump power.
UNIT_PUMP_MOTOR_P2_KW = 2.20
UNIT_PUMP_PDS_EFFICIENCY = 0.901
UNIT_PUMP_ELECTRICAL_REFERENCE_KW = (
    UNIT_PUMP_MOTOR_P2_KW / UNIT_PUMP_PDS_EFFICIENCY
)
# Pump affinity screening.
PUMP_POWER_EXPONENT = 3.0
PUMP_MOTOR_LOAD_FACTOR = 1.0

# The larger MGE132MH common pump remains excluded 


# ============================================================
# 11. CIRCUIT / PLANT DISPATCH SETTINGS
# ============================================================

DISPATCH_LOAD_STEP_KW = 1.0

# Candidate installed fan operating fractions considered when optimizing a unit.
# Finer fan-speed resolution avoids artificial point-to-point jumps when the
# dispatch optimizer changes between neighbouring fan settings.
DISPATCH_FAN_CANDIDATES = [
    0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70,
    0.75, 0.80, 0.85, 0.90, 0.95, 1.00,
]

# The final project distinguishes physical C1/C2 identity from staging.
# Dispatch uses "one active circuit" versus "two active circuits".
SECOND_CIRCUIT_SWITCH_POWER_ADVANTAGE_KW = 0.10


# ============================================================
# 12. BUFFER-TANK SCREENING SETTINGS
# ============================================================

BUFFER_TANK_HEATING_INSTALLED_L = 1000.0
BUFFER_TANK_COOLING_INSTALLED_L = 2000.0
BUFFER_DEADBAND_K = 2.0

BUFFER_HEATING_VOLUME_STUDY_L = [
    250.0, 500.0, 750.0, 1000.0, 1500.0, 2000.0, 2500.0, 3000.0, 4000.0
]

BUFFER_COOLING_VOLUME_STUDY_L = [
    250.0, 500.0, 750.0, 1000.0, 1500.0, 2000.0, 2500.0, 3000.0, 4000.0
]

BUFFER_LOAD_FRACTIONS_OF_QMIN = [
    0.10, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60, 0.70, 0.75, 0.80, 0.90
]


# ============================================================
# 13. CARNOT / SECOND-LAW SETTINGS
# ============================================================

CARNOT_START_DATE = "2026-07-01"
CARNOT_END_DATE_EXCLUSIVE = "2026-08-01"

# The external/system-level Carnot benchmark uses outdoor dry-bulb and the
# arithmetic mean of entering/leaving water temperature. It is a reservoir
# benchmark, not a Lorenz-cycle calculation.


# ============================================================
# 14. STANDARDIZED ACTIVE-MODE SEASONAL SETTINGS
# ============================================================

STANDARD_HEATING_WATER_OUT_C = 50.0
STANDARD_COOLING_WATER_OUT_C = 7.0

STANDARD_HEATING_TDESIGN_C = -10.0

# Conservative screening TOL retained from the prior thesis analysis until the
# actual Euroklimat product operating limit is confirmed.
STANDARD_HEATING_TOL_C = -7.0

STANDARD_COOLING_TDESIGN_C = 35.0

STANDARD_CYCLING_DEGRADATION_COEFFICIENT = 0.25

STANDARD_HEATING_ANCHOR_OUTDOOR_C = [
    -7.0,
    2.0,
    7.0,
    12.0,
]

STANDARD_COOLING_ANCHOR_OUTDOOR_C = [
    20.0,
    25.0,
    30.0,
    35.0,
]

# Commission Regulation (EU) No 813/2013, average heating climate.
STANDARD_HEATING_BIN_HOURS = {
    -10: 1,
    -9: 25,
    -8: 23,
    -7: 24,
    -6: 27,
    -5: 68,
    -4: 91,
    -3: 89,
    -2: 165,
    -1: 173,
    0: 240,
    1: 280,
    2: 320,
    3: 357,
    4: 356,
    5: 303,
    6: 330,
    7: 326,
    8: 348,
    9: 335,
    10: 315,
    11: 215,
    12: 169,
    13: 151,
    14: 105,
    15: 74,
}

# Commission Regulation (EU) 2016/2281 cooling reference bins.
STANDARD_COOLING_BIN_HOURS = {
    17: 205,
    18: 227,
    19: 225,
    20: 225,
    21: 216,
    22: 215,
    23: 218,
    24: 197,
    25: 178,
    26: 158,
    27: 137,
    28: 109,
    29: 88,
    30: 63,
    31: 39,
    32: 31,
    33: 24,
    34: 17,
    35: 13,
    36: 9,
    37: 4,
    38: 3,
    39: 1,
    40: 0,
}


# ============================================================
# 15. ANNUAL KIONA RAW-DATA SETTINGS
# ============================================================

# All matching annual raw exports are merged chronologically. Overlapping
# timestamps are de-duplicated, keeping the value from the later file.
ANNUAL_RAW_GLOB = "Kiona_Annual_*.csv"

ANNUAL_SIGNAL_VALID_FROM = {
    "SH_320001_OE405_VS_PV": "2026-05-21 10:45:00",
    "SH_320001_OE405_RE_PV": "2026-02-09 10:20:00",
    "SH_320001_OE404_RE_PV": "2026-02-09 10:20:00",
    "SH_320001_OE404_RT511_PV": "2026-05-21 10:15:00",
    "SH_320001_OE404_VS_PV": "2026-05-21 10:40:00",
    "SH_320001_OE404_RT411_PV": "2026-05-21 10:10:00",
}

ANNUAL_VENT_HEATING_SETPOINT_MIN_C = 30.0
ANNUAL_VENT_COOLING_SETPOINT_MAX_C = 15.0

ANNUAL_HAMPEL_WINDOW_SAMPLES = 13
ANNUAL_HAMPEL_MAD_FACTOR = 4.0
ANNUAL_HAMPEL_MIN_ABS_SPIKE_KW = 10.0

ANNUAL_OUTDOOR_BIN_C = 1.0
ANNUAL_MIN_TREND_BIN_SAMPLES = 12
ANNUAL_TREND_ROLLING_BINS = 5

ANNUAL_MONTHLY_START_YEAR = 2026
ANNUAL_MONTHLY_START_MONTH = 2
ANNUAL_MONTHLY_END_YEAR = 2026
ANNUAL_MONTHLY_END_MONTH = 7


# ============================================================
# 16. HYBRID-OPERATION SETTINGS
# ============================================================

HYBRID_START_YEAR = 2026
HYBRID_START_MONTH = 2
HYBRID_END_YEAR = 2026
HYBRID_END_MONTH = 7
HYBRID_ACTIVE_LOAD_THRESHOLD_KW = 5.0


# ============================================================
# 17. ANNUAL RECONSTRUCTION / PLANT SETTINGS
# ============================================================

# The previously validated annual / hybrid / mixed-size scripts used 0.80.
# Keep this annual-study assumption explicit instead of silently using
# the 0.60 exponent employed by some general parametric studies.
ANNUAL_AIR_HT_EXPONENT = 0.80


ANNUAL_RECONSTRUCTION_MIN_COMPONENT_BIN_SAMPLES = 12
ANNUAL_RECONSTRUCTION_TREND_ROLLING_BINS = 5
ANNUAL_PLANT_HEATING_WATER_OUT_C = 50.0
ANNUAL_PLANT_COOLING_WATER_OUT_C = 7.0
ANNUAL_PLANT_CYCLING_DEGRADATION_COEFFICIENT = 0.15
ANNUAL_PLANT_LOAD_BIN_KW = 2.5
ANNUAL_PLANT_OUTDOOR_BIN_C = 1.0

# ============================================================
# 18. WATER/WATER HEAT-RECOVERY SCREENING
# ============================================================

HEAT_RECOVERY_UA_MULTIPLIER = 1.00
HEAT_RECOVERY_MAX_CIRCUITS = 2
HEAT_RECOVERY_LOAD_BIN_KW = 5.0
HEAT_RECOVERY_RESIDUAL_LOAD_BIN_KW = 2.5
HEAT_RECOVERY_TEMPERATURE_BIN_K = 1.0
HEAT_RECOVERY_FREQUENCY_STEP_HZ = 2.5


# ============================================================
# 19. MIXED SMALL + LARGE HERA SCREENING
# ============================================================

# Dense parameter sweeps for thesis figures.
# Small-unit sizing: 2.5 percentage-point increments from 20% to 100%.
MIXED_SMALL_UNIT_SIZE_FACTORS = [0.2, 0.225, 0.25, 0.275, 0.3, 0.325, 0.35, 0.375, 0.4, 0.425, 0.45, 0.475, 0.5, 0.525, 0.55, 0.575, 0.6, 0.625, 0.65, 0.675, 0.7, 0.725, 0.75, 0.775, 0.8, 0.825, 0.85, 0.875, 0.9, 0.925, 0.95, 0.975, 1.0]
MIXED_REFERENCE_FLEET = [1.0,1.0,1.0]
MIXED_CYCLING_DEGRADATION_COEFFICIENT = 0.15

MIXED_ACTIVE_LOAD_THRESHOLD_KW = 5.0
MIXED_MODEL_LOAD_BIN_KW = 5.0
MIXED_MODEL_TEMPERATURE_BIN_K = 1.0
MIXED_MODEL_FREQUENCY_STEP_HZ = 2.5
# Cd sensitivity: 0.025 increments from 0.00 to 0.30.
MIXED_CYCLING_DEGRADATION_SENSITIVITY = [0.0, 0.025, 0.05, 0.075, 0.1, 0.125, 0.15, 0.175, 0.2, 0.225, 0.25, 0.275, 0.3]
MIXED_REQUIRE_100_PERCENT_REFERENCE_COVERAGE = True
SOURCE_TIMESTEP_MINUTES = 5.0

# Convenience master-run flags remain in run_thesis_model.py.
