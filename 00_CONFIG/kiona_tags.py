"""
Central Kiona signal mapping.

"""

# ============================================================
# 1. UNIT MODES USED FOR THE VALIDATION DATASET
# ============================================================

UNIT_MODE = {
    1: "heating",
    2: "cooling",
}


# ============================================================
# 2. OUTDOOR SIGNAL
# ============================================================

OUTDOOR_TAG = "SH_320001_RT090_MV"


# ============================================================
# 3. DETAILED UNIT SIGNALS
# ============================================================

UNIT_TAGS = {
    1: {
        "electrical_power_kW": "SH_320001_OE002_KW_EL_MV1_PV",
        "working_setpoint": "SH_320001_IK001_SPK",
        "capacity_request_percent": "SH_320001_IK001_C",
        "suction_temp_c1_C": "SH_320001_IK001_MV10_PV",
        "suction_temp_c2_C": "SH_320001_IK001_MV17_PV",
        "condensing_pressure_c1_bar": "SH_320001_IK001_MV5_PV",
        "condensing_pressure_c2_bar": "SH_320001_IK001_MV12_PV",
        "evaporating_pressure_c1_bar": "SH_320001_IK001_MV6_PV",
        "evaporating_pressure_c2_bar": "SH_320001_IK001_MV13_PV",
        "superheat_c1_K": "SH_320001_IK001_MV11_PV",
        "superheat_c2_K": "SH_320001_IK001_MV18_PV",
        "hot_side_out_C": "SH_320001_IK001_MV1_PV",
        "hot_side_in_C": "SH_320001_IK001_MV2_PV",
        "runtime_counter_c1": "SH_320001_IK001_TID1_PV",
        "runtime_counter_c2": "SH_320001_IK001_TID2_PV",
        "fan_signal_c1_percent": "SH_320001_IK001_C1_PV",
        "fan_signal_c2_percent": "SH_320001_IK001_C2_PV",
    },
    2: {
        "electrical_power_kW": "SH_320001_OE001_KW_EL_MV2_PV",
        "working_setpoint": "SH_320001_IK002_SPK",
        "capacity_request_percent": "SH_320001_IK002_C",
        "suction_temp_c1_C": "SH_320001_IK002_MV10_PV",
        "suction_temp_c2_C": "SH_320001_IK002_MV17_PV",
        "condensing_pressure_c1_bar": "SH_320001_IK002_MV5_PV",
        "condensing_pressure_c2_bar": "SH_320001_IK002_MV12_PV",
        "evaporating_pressure_c1_bar": "SH_320001_IK002_MV6_PV",
        "evaporating_pressure_c2_bar": "SH_320001_IK002_MV13_PV",
        "superheat_c1_K": "SH_320001_IK002_MV11_PV",
        "superheat_c2_K": "SH_320001_IK002_MV18_PV",
        "hot_side_out_C": "SH_320001_IK002_MV1_PV",
        "hot_side_in_C": "SH_320001_IK002_MV2_PV",
        "runtime_counter_c1": "SH_320001_IK002_TID1_PV",
        "runtime_counter_c2": "SH_320001_IK002_TID2_PV",
        "fan_signal_c1_percent": "SH_320001_IK002_C1_PV",
        "fan_signal_c2_percent": "SH_320001_IK002_C2_PV",
    },
}
