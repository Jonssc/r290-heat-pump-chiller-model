"""
seasonal_performance_model.py

Pure active-mode seasonal calculation helpers used by the standardized
SCOPon / SEERon screening.

No files or plots are handled in this module.
"""

# ============================================================
# 1. IMPORTS
# ============================================================

import numpy as np


# ============================================================
# 2. LOAD FRACTIONS
# ============================================================

def heating_part_load_fraction(
    outdoor_C,
    design_outdoor_C=-10.0,
    balance_temperature_C=16.0,
):
    """Linear regulation load relation used in the seasonal screening."""
    T = np.asarray(outdoor_C, dtype=float)

    denominator = (
        design_outdoor_C
        - balance_temperature_C
    )

    result = (
        T
        - balance_temperature_C
    ) / denominator

    return np.clip(
        result,
        0.0,
        1.0,
    )


def cooling_part_load_fraction(
    outdoor_C,
    design_outdoor_C=35.0,
    zero_load_temperature_C=16.0,
):
    T = np.asarray(outdoor_C, dtype=float)

    denominator = (
        design_outdoor_C
        - zero_load_temperature_C
    )

    result = (
        T
        - zero_load_temperature_C
    ) / denominator

    return np.clip(
        result,
        0.0,
        1.0,
    )


# ============================================================
# 3. CYCLING DEGRADATION
# ============================================================

def part_load_factor(
    part_load_ratio,
    degradation_coefficient=0.25,
):
    PLR = np.asarray(
        part_load_ratio,
        dtype=float,
    )

    Cd = float(
        degradation_coefficient
    )

    return (
        1.0
        - Cd
        * (
            1.0
            - PLR
        )
    )


def cycling_average_power_kW(
    required_load_kW,
    minimum_capacity_kW,
    minimum_input_power_kW,
    degradation_coefficient=0.25,
):
    """Average input below minimum continuous capacity.

    PLR is defined against minimum available thermal capacity.
    """
    load = np.asarray(
        required_load_kW,
        dtype=float,
    )

    qmin = float(
        minimum_capacity_kW
    )

    pmin = float(
        minimum_input_power_kW
    )

    with np.errstate(
        divide="ignore",
        invalid="ignore",
    ):
        PLR = load / qmin

    PLR = np.clip(
        PLR,
        0.0,
        1.0,
    )

    PLF = part_load_factor(
        PLR,
        degradation_coefficient,
    )

    with np.errstate(
        divide="ignore",
        invalid="ignore",
    ):
        power = (
            PLR
            * pmin
            / PLF
        )

    return power


# ============================================================
# 4. ACTIVE-MODE SEASONAL INDEX
# ============================================================

def seasonal_index(
    useful_energy_kWh,
    electrical_energy_kWh,
):
    useful = float(
        useful_energy_kWh
    )

    electrical = float(
        electrical_energy_kWh
    )

    if electrical <= 0:
        return np.nan

    return useful / electrical
