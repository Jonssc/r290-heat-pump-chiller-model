"""
heat_recovery_model.py

Pure dedicated R290 water/water heat-recovery screening functions.

The model uses:
- the existing Frascold compressor database;
- the field-calibrated liquid-side effective UAs;
- no outdoor-coil fan;
- 1 or 2 refrigerant circuits;
- no product-specific water/water manufacturer map.

No files and no plots are handled here.
"""

# ============================================================
# 1. IMPORTS
# ============================================================

from __future__ import annotations

from functools import lru_cache

import numpy as np


# ============================================================
# 2. ONE WATER/WATER CIRCUIT CURVE
# ============================================================

@lru_cache(maxsize=None)
def water_water_circuit_curve(
    frascold_lookup,
    *,
    cooling_water_out_C: float,
    heating_water_out_C: float,
    evaporator_UA_kW_K: float,
    condenser_UA_kW_K: float,
    reference_cooling_water_approach_K: float,
    reference_heating_water_approach_K: float,
    minimum_frequency_Hz: float = 30.0,
    maximum_frequency_Hz: float = 70.0,
    frequency_step_Hz: float = 2.5,
    maximum_iterations: int = 80,
    tolerance_K: float = 1e-4,
):
    """Return the 30...70 Hz water/water curve for one R290 circuit."""

    frequencies = np.arange(
        minimum_frequency_Hz,
        maximum_frequency_Hz
        + 0.5 * frequency_step_Hz,
        frequency_step_Hz,
    )

    rows = []

    for frequency_Hz in frequencies:
        T_evap = (
            float(cooling_water_out_C)
            - float(
                reference_cooling_water_approach_K
            )
        )

        T_cond = (
            float(heating_water_out_C)
            + float(
                reference_heating_water_approach_K
            )
        )

        valid = True
        converged = False

        for _ in range(
            int(maximum_iterations)
        ):
            try:
                performance = (
                    frascold_lookup.interpolate(
                        float(T_evap),
                        float(T_cond),
                        float(frequency_Hz),
                    )
                )
            except Exception:
                valid = False
                break

            Q_evap = float(
                performance[
                    "evaporator_capacity_kW"
                ]
            )

            Q_cond = float(
                performance[
                    "condenser_capacity_kW"
                ]
            )

            new_T_evap = (
                float(cooling_water_out_C)
                - Q_evap
                / float(
                    evaporator_UA_kW_K
                )
            )

            new_T_cond = (
                float(heating_water_out_C)
                + Q_cond
                / float(
                    condenser_UA_kW_K
                )
            )

            next_T_evap = (
                0.60 * T_evap
                + 0.40 * new_T_evap
            )

            next_T_cond = (
                0.60 * T_cond
                + 0.40 * new_T_cond
            )

            if max(
                abs(
                    next_T_evap
                    - T_evap
                ),
                abs(
                    next_T_cond
                    - T_cond
                ),
            ) < float(
                tolerance_K
            ):
                T_evap = next_T_evap
                T_cond = next_T_cond
                converged = True
                break

            T_evap = next_T_evap
            T_cond = next_T_cond

        if not valid:
            continue

        try:
            performance = (
                frascold_lookup.interpolate(
                    float(T_evap),
                    float(T_cond),
                    float(frequency_Hz),
                )
            )
        except Exception:
            continue

        rows.append({
            "frequency_Hz": float(
                frequency_Hz
            ),
            "Q_evap_kW": float(
                performance[
                    "evaporator_capacity_kW"
                ]
            ),
            "Q_cond_kW": float(
                performance[
                    "condenser_capacity_kW"
                ]
            ),
            "P_comp_kW": float(
                performance[
                    "compressor_power_kW"
                ]
            ),
            "T_evap_C": float(
                T_evap
            ),
            "T_cond_C": float(
                T_cond
            ),
            "iteration_converged": bool(
                converged
            ),
        })

    return rows


# ============================================================
# 3. BEST WATER/WATER + RESIDUAL AIR/WATER DISPATCH
# ============================================================

@lru_cache(maxsize=None)
def best_heat_recovery_operation(
    *,
    frascold_lookup,
    annual_plant_module,
    circuit_model,
    heating_load_kW: float,
    cooling_load_kW: float,
    outdoor_C: float,
    heating_water_out_C: float,
    cooling_water_out_C: float,
    evaporator_UA_kW_K: float,
    condenser_UA_kW_K: float,
    reference_cooling_water_approach_K: float,
    reference_heating_water_approach_K: float,
    existing_fleet_tuple=(1.0, 1.0, 1.0),
    maximum_water_water_circuits: int = 2,
    frequency_step_Hz: float = 2.5,
    residual_load_bin_kW: float = 2.5,
):
    """Find lowest total power among all candidate water/water operating points.

    The duty fraction is limited simultaneously by available cooling and
    heating demand:
        duty <= Qcool / Qevap
        duty <= Qheat / Qcond
    """

    q_heat = max(
        float(heating_load_kW),
        0.0,
    )

    q_cool = max(
        float(cooling_load_kW),
        0.0,
    )

    baseline = annual_plant_module.fleet_dispatch(
        circuit_model,
        tuple(existing_fleet_tuple),
        q_heat,
        q_cool,
        float(outdoor_C),
        float(heating_water_out_C),
        float(cooling_water_out_C),
        0.0,  # validated previous heat-recovery study used ideal cycling
        frequency_step_Hz,
    )

    if (
        baseline.get("model_status")
        != "OK"
        or float(
            baseline.get(
                "total_shortfall_kW",
                0.0,
            )
        )
        > 1e-9
    ):
        return {
            "model_status":
                "AIR_WATER_REFERENCE_INFEASIBLE"
        }

    baseline_power = float(
        baseline[
            "plant_power_kW"
        ]
    )

    best = {
        "model_status": "OK",
        "total_power_kW": baseline_power,
        "reference_air_water_power_kW": baseline_power,
        "water_water_power_kW": 0.0,
        "water_water_duty_fraction": 0.0,
        "water_water_circuits": 0,
        "water_water_frequency_Hz": 0.0,
        "recovered_cooling_kW": 0.0,
        "recovered_heating_kW": 0.0,
        "residual_heating_kW": q_heat,
        "residual_cooling_kW": q_cool,
        "residual_air_water_power_kW":
            baseline_power,
        "electrical_saving_kW": 0.0,
    }

    curve = water_water_circuit_curve(
        frascold_lookup,
        cooling_water_out_C=
            cooling_water_out_C,
        heating_water_out_C=
            heating_water_out_C,
        evaporator_UA_kW_K=
            evaporator_UA_kW_K,
        condenser_UA_kW_K=
            condenser_UA_kW_K,
        reference_cooling_water_approach_K=
            reference_cooling_water_approach_K,
        reference_heating_water_approach_K=
            reference_heating_water_approach_K,
        minimum_frequency_Hz=
            circuit_model.min_frequency_Hz,
        maximum_frequency_Hz=
            circuit_model.max_frequency_Hz,
        frequency_step_Hz=
            frequency_step_Hz,
    )

    for circuits in range(
        1,
        int(
            maximum_water_water_circuits
        )
        + 1,
    ):
        for point in curve:
            Q_evap = (
                circuits
                * float(
                    point[
                        "Q_evap_kW"
                    ]
                )
            )

            Q_cond = (
                circuits
                * float(
                    point[
                        "Q_cond_kW"
                    ]
                )
            )

            P_comp = (
                circuits
                * float(
                    point[
                        "P_comp_kW"
                    ]
                )
            )

            if (
                Q_evap <= 0
                or Q_cond <= 0
            ):
                continue

            duty_fraction = min(
                1.0,
                (
                    q_cool
                    / Q_evap
                    if Q_evap > 0
                    else 0.0
                ),
                (
                    q_heat
                    / Q_cond
                    if Q_cond > 0
                    else 0.0
                ),
            )

            if duty_fraction <= 0:
                continue

            recovered_cooling = (
                duty_fraction
                * Q_evap
            )

            recovered_heating = (
                duty_fraction
                * Q_cond
            )

            residual_heating = max(
                q_heat
                - recovered_heating,
                0.0,
            )

            residual_cooling = max(
                q_cool
                - recovered_cooling,
                0.0,
            )

            # Round residual demand to the validated 2.5 kW plant-dispatch grid.
            if (
                residual_heating
                <= 0.5
                * residual_load_bin_kW
            ):
                residual_heating = 0.0
            else:
                residual_heating = (
                    round(
                        residual_heating
                        / residual_load_bin_kW
                    )
                    * residual_load_bin_kW
                )

            if (
                residual_cooling
                <= 0.5
                * residual_load_bin_kW
            ):
                residual_cooling = 0.0
            else:
                residual_cooling = (
                    round(
                        residual_cooling
                        / residual_load_bin_kW
                    )
                    * residual_load_bin_kW
                )

            if (
                residual_heating > 0
                or residual_cooling > 0
            ):
                residual = (
                    annual_plant_module.fleet_dispatch(
                        circuit_model,
                        tuple(
                            existing_fleet_tuple
                        ),
                        residual_heating,
                        residual_cooling,
                        float(outdoor_C),
                        float(
                            heating_water_out_C
                        ),
                        float(
                            cooling_water_out_C
                        ),
                        0.0,
                        frequency_step_Hz,
                    )
                )

                if (
                    residual.get(
                        "model_status"
                    )
                    != "OK"
                    or float(
                        residual.get(
                            "total_shortfall_kW",
                            0.0,
                        )
                    )
                    > 1e-9
                ):
                    continue

                residual_power = float(
                    residual[
                        "plant_power_kW"
                    ]
                )

            else:
                residual_power = 0.0

            water_water_power = (
                duty_fraction
                * P_comp
            )

            total_power = (
                water_water_power
                + residual_power
            )

            if (
                total_power
                < best[
                    "total_power_kW"
                ]
            ):
                best = {
                    "model_status": "OK",
                    "total_power_kW":
                        float(total_power),
                    "reference_air_water_power_kW":
                        baseline_power,
                    "water_water_power_kW":
                        float(
                            water_water_power
                        ),
                    "water_water_duty_fraction":
                        float(
                            duty_fraction
                        ),
                    "water_water_circuits":
                        int(
                            circuits
                        ),
                    "water_water_frequency_Hz":
                        float(
                            point[
                                "frequency_Hz"
                            ]
                        ),
                    "recovered_cooling_kW":
                        float(
                            recovered_cooling
                        ),
                    "recovered_heating_kW":
                        float(
                            recovered_heating
                        ),
                    "residual_heating_kW":
                        float(
                            residual_heating
                        ),
                    "residual_cooling_kW":
                        float(
                            residual_cooling
                        ),
                    "residual_air_water_power_kW":
                        float(
                            residual_power
                        ),
                    "electrical_saving_kW":
                        float(
                            baseline_power
                            - total_power
                        ),
                }

    return best
