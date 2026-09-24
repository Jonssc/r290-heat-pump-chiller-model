"""
carnot_model.py

Pure thermodynamic benchmark functions.
No files, plots or project-specific data loading.
"""

# ============================================================
# 1. IMPORTS
# ============================================================

import numpy as np


# ============================================================
# 2. CARNOT PERFORMANCE
# ============================================================

def heating_COP_carnot(T_evap_C, T_cond_C):
    Te = np.asarray(T_evap_C, dtype=float) + 273.15
    Tc = np.asarray(T_cond_C, dtype=float) + 273.15

    with np.errstate(divide="ignore", invalid="ignore"):
        result = Tc / (Tc - Te)

    result = np.where(
        (Tc > Te) & (Te > 0),
        result,
        np.nan,
    )

    return result


def cooling_EER_carnot(T_evap_C, T_cond_C):
    Te = np.asarray(T_evap_C, dtype=float) + 273.15
    Tc = np.asarray(T_cond_C, dtype=float) + 273.15

    with np.errstate(divide="ignore", invalid="ignore"):
        result = Te / (Tc - Te)

    result = np.where(
        (Tc > Te) & (Te > 0),
        result,
        np.nan,
    )

    return result


def carnot_performance(mode, T_evap_C, T_cond_C):
    mode = str(mode).strip().lower()

    if mode == "heating":
        return heating_COP_carnot(
            T_evap_C,
            T_cond_C,
        )

    if mode == "cooling":
        return cooling_EER_carnot(
            T_evap_C,
            T_cond_C,
        )

    raise ValueError(
        "mode must be heating or cooling"
    )


# ============================================================
# 3. REVERSIBLE MINIMUM WORK
# ============================================================

def reversible_power_kW(
    mode,
    useful_capacity_kW,
    T_evap_C,
    T_cond_C,
):
    performance = carnot_performance(
        mode,
        T_evap_C,
        T_cond_C,
    )

    with np.errstate(divide="ignore", invalid="ignore"):
        result = (
            np.asarray(useful_capacity_kW, dtype=float)
            / performance
        )

    return result


def equivalent_carnot_performance(
    total_useful_capacity_kW,
    total_reversible_power_kW,
):
    with np.errstate(divide="ignore", invalid="ignore"):
        result = (
            np.asarray(total_useful_capacity_kW, dtype=float)
            / np.asarray(total_reversible_power_kW, dtype=float)
        )

    return result


def second_law_efficiency_percent(
    reversible_power_kW,
    actual_power_kW,
):
    with np.errstate(divide="ignore", invalid="ignore"):
        result = (
            100.0
            * np.asarray(reversible_power_kW, dtype=float)
            / np.asarray(actual_power_kW, dtype=float)
        )

    return result
