"""
annual_plant_model.py

Fast cached plant-dispatch model for annual, hybrid and mixed-size analyses.

This module does NOT read files and does NOT make plots.

A physical HERA can be:
    OFF
    HEATING with 1 circuit
    HEATING with 2 circuits
    COOLING with 1 circuit
    COOLING with 2 circuits

A physical unit cannot heat and cool simultaneously.
"""

# ============================================================
# 1. IMPORTS
# ============================================================

from __future__ import annotations

from functools import lru_cache
import itertools

import numpy as np


# ============================================================
# 2. ONE-CIRCUIT PERFORMANCE CURVE
# ============================================================

@lru_cache(maxsize=None)
def base_circuit_curve(
    circuit_model,
    mode: str,
    outdoor_C: float,
    water_out_C: float,
    frequency_step_Hz: float = 2.5,
):
    """Return one existing full-size HERA circuit across 30...70 Hz."""

    fan_speed = float(
        circuit_model.cal[mode].reference_fan_speed_fraction
    )

    frequencies = np.arange(
        circuit_model.min_frequency_Hz,
        circuit_model.max_frequency_Hz + 0.5 * frequency_step_Hz,
        frequency_step_Hz,
    )

    rows = []

    for frequency_Hz in frequencies:
        result = circuit_model.safe_evaluate(
            circuit_model.case_class(
                mode=mode,
                outdoor_C=float(outdoor_C),
                water_out_C=float(water_out_C),
                frequency_Hz=float(frequency_Hz),
                fan_speed_fraction=fan_speed,
            )
        )

        if result.get("model_status") != "OK":
            continue

        rows.append(
            (
                float(frequency_Hz),
                float(result["Quseful_kW"]),
                float(result["Pcircuit_comp_plus_fan_kW"]),
            )
        )

    return tuple(rows)


def curve_arrays(
    circuit_model,
    mode: str,
    outdoor_C: float,
    water_out_C: float,
    frequency_step_Hz: float = 2.5,
):
    raw = base_circuit_curve(
        circuit_model,
        mode,
        float(outdoor_C),
        float(water_out_C),
        float(frequency_step_Hz),
    )

    if not raw:
        return None

    array = np.asarray(raw, dtype=float)

    return (
        array[:, 0],
        array[:, 1],
        array[:, 2],
    )


# ============================================================
# 3. PHYSICAL FLEET STATE ENUMERATION
# ============================================================

@lru_cache(maxsize=None)
def effective_scale_pairs(fleet_tuple):
    """Enumerate physically possible simultaneous heating/cooling states."""

    fleet = tuple(
        float(value)
        for value in fleet_tuple
    )

    unit_states = (
        ("off", 0),
        ("heating", 1),
        ("heating", 2),
        ("cooling", 1),
        ("cooling", 2),
    )

    pairs = set()

    for states in itertools.product(
        unit_states,
        repeat=len(fleet),
    ):
        heating_scale = 0.0
        cooling_scale = 0.0

        for size_factor, state in zip(
            fleet,
            states,
        ):
            mode = state[0]
            active_circuits = int(
                state[1]
            )

            if mode == "heating":
                heating_scale += (
                    size_factor
                    * active_circuits
                )

            elif mode == "cooling":
                cooling_scale += (
                    size_factor
                    * active_circuits
                )

        pairs.add(
            (
                round(
                    heating_scale,
                    6,
                ),
                round(
                    cooling_scale,
                    6,
                ),
            )
        )

    return tuple(
        sorted(
            pairs
        )
    )


# ============================================================
# 4. PART-LOAD / CYCLING MODEL
# ============================================================

@lru_cache(maxsize=None)
def mode_power_with_shortfall(
    circuit_model,
    mode: str,
    load_kW: float,
    effective_circuit_scale: float,
    outdoor_C: float,
    water_out_C: float,
    cycling_degradation_coefficient: float,
    frequency_step_Hz: float = 2.5,
):
    """Electrical power for one heating or cooling side of the plant."""

    required_load = float(
        load_kW
    )

    scale = float(
        effective_circuit_scale
    )

    Cd = float(
        cycling_degradation_coefficient
    )

    if required_load <= 0:
        return (
            0.0,
            0.0,
            0.0,
            False,
            0.0,
            0.0,
            0.0,
            0.0,
        )

    if scale <= 0:
        return (
            0.0,
            0.0,
            required_load,
            False,
            0.0,
            0.0,
            0.0,
            0.0,
        )

    arrays = curve_arrays(
        circuit_model,
        mode,
        outdoor_C,
        water_out_C,
        frequency_step_Hz,
    )

    if arrays is None:
        return None

    frequency_Hz, Q_base, P_base = arrays

    Q = (
        scale
        * Q_base
    )

    P = (
        scale
        * P_base
    )

    Q_min = float(
        Q[0]
    )

    Q_max = float(
        Q[-1]
    )

    P_min = float(
        P[0]
    )

    # Below 30-Hz continuous capacity.
    if required_load < Q_min:
        PLR = (
            required_load
            / Q_min
        )

        PLF = max(
            1.0
            - Cd
            * (
                1.0
                - PLR
            ),
            0.05,
        )

        power_kW = (
            PLR
            * P_min
            / PLF
        )

        return (
            float(
                power_kW
            ),
            required_load,
            0.0,
            True,
            float(
                PLR
            ),
            float(
                frequency_Hz[0]
            ),
            Q_min,
            Q_max,
        )

    # Inside the 30...70 Hz capacity range.
    if required_load <= Q_max:
        return (
            float(
                np.interp(
                    required_load,
                    Q,
                    P,
                )
            ),
            required_load,
            0.0,
            False,
            1.0,
            float(
                np.interp(
                    required_load,
                    Q,
                    frequency_Hz,
                )
            ),
            Q_min,
            Q_max,
        )

    # Capacity-limited. Never extrapolate Frascold.
    return (
        float(
            P[-1]
        ),
        Q_max,
        required_load - Q_max,
        False,
        1.0,
        float(
            frequency_Hz[-1]
        ),
        Q_min,
        Q_max,
    )


# ============================================================
# 5. VECTORIZED MODE RESULTS FOR ALL EFFECTIVE SCALES
# ============================================================

def mode_results_for_scales(
    circuit_model,
    mode,
    load_kW,
    scales,
    outdoor_C,
    water_out_C,
    cycling_degradation_coefficient,
    frequency_step_Hz,
):
    """Evaluate one mode for several effective circuit scales at once."""

    required_load = max(
        float(
            load_kW
        ),
        0.0,
    )

    scales = np.asarray(
        scales,
        dtype=float,
    )

    count = len(
        scales
    )

    power = np.full(
        count,
        np.inf,
        dtype=float,
    )

    shortfall = np.full(
        count,
        np.inf,
        dtype=float,
    )

    cycling = np.zeros(
        count,
        dtype=bool,
    )

    PLR = np.zeros(
        count,
        dtype=float,
    )

    frequency = np.zeros(
        count,
        dtype=float,
    )

    Qmin = np.zeros(
        count,
        dtype=float,
    )

    Qmax = np.zeros(
        count,
        dtype=float,
    )

    # A zero load is served only by the zero-scale state.
    if required_load <= 0:
        zero = np.isclose(
            scales,
            0.0,
        )

        power[
            zero
        ] = 0.0

        shortfall[
            zero
        ] = 0.0

        return {
            "power_kW": power,
            "shortfall_kW": shortfall,
            "cycling": cycling,
            "PLR": PLR,
            "frequency_Hz": frequency,
            "Qmin_kW": Qmin,
            "Qmax_kW": Qmax,
        }

    arrays = curve_arrays(
        circuit_model,
        mode,
        outdoor_C,
        water_out_C,
        frequency_step_Hz,
    )

    if arrays is None:
        return {
            "power_kW": power,
            "shortfall_kW": shortfall,
            "cycling": cycling,
            "PLR": PLR,
            "frequency_Hz": frequency,
            "Qmin_kW": Qmin,
            "Qmax_kW": Qmax,
        }

    base_frequency, Q_base, P_base = arrays

    positive_indices = np.where(
        scales > 0
    )[0]

    Cd = float(
        cycling_degradation_coefficient
    )

    for index in positive_indices:
        scale = float(
            scales[
                index
            ]
        )

        q_min = (
            scale
            * float(
                Q_base[0]
            )
        )

        q_max = (
            scale
            * float(
                Q_base[-1]
            )
        )

        p_min = (
            scale
            * float(
                P_base[0]
            )
        )

        Qmin[
            index
        ] = q_min

        Qmax[
            index
        ] = q_max

        # Below minimum continuous capacity.
        if required_load < q_min:
            plr = (
                required_load
                / q_min
            )

            plf = max(
                1.0
                - Cd
                * (
                    1.0
                    - plr
                ),
                0.05,
            )

            power[
                index
            ] = (
                plr
                * p_min
                / plf
            )

            shortfall[
                index
            ] = 0.0

            cycling[
                index
            ] = True

            PLR[
                index
            ] = plr

            frequency[
                index
            ] = float(
                base_frequency[0]
            )

            continue

        # Inside continuous-capacity range.
        if required_load <= q_max:
            normalized_load = (
                required_load
                / scale
            )

            power[
                index
            ] = (
                scale
                * float(
                    np.interp(
                        normalized_load,
                        Q_base,
                        P_base,
                    )
                )
            )

            shortfall[
                index
            ] = 0.0

            PLR[
                index
            ] = 1.0

            frequency[
                index
            ] = float(
                np.interp(
                    normalized_load,
                    Q_base,
                    base_frequency,
                )
            )

            continue

        # Capacity limited at 70 Hz.
        power[
            index
        ] = (
            scale
            * float(
                P_base[-1]
            )
        )

        shortfall[
            index
        ] = (
            required_load
            - q_max
        )

        PLR[
            index
        ] = 1.0

        frequency[
            index
        ] = float(
            base_frequency[-1]
        )

    return {
        "power_kW": power,
        "shortfall_kW": shortfall,
        "cycling": cycling,
        "PLR": PLR,
        "frequency_Hz": frequency,
        "Qmin_kW": Qmin,
        "Qmax_kW": Qmax,
    }


# ============================================================
# 6. LOWEST-POWER PHYSICAL FLEET DISPATCH
# ============================================================

@lru_cache(maxsize=None)
def fleet_dispatch(
    circuit_model,
    fleet_tuple,
    heating_load_kW: float,
    cooling_load_kW: float,
    outdoor_C: float,
    heating_water_out_C: float,
    cooling_water_out_C: float,
    cycling_degradation_coefficient: float = 0.15,
    frequency_step_Hz: float = 2.5,
):
    """Find the lowest-power physical fleet state at the requested loads."""

    heating_load = max(
        float(
            heating_load_kW
        ),
        0.0,
    )

    cooling_load = max(
        float(
            cooling_load_kW
        ),
        0.0,
    )

    pairs = np.asarray(
        effective_scale_pairs(
            tuple(
                fleet_tuple
            )
        ),
        dtype=float,
    )

    if pairs.size == 0:
        return {
            "model_status":
                "OUTSIDE_MODEL_DOMAIN",
            "total_shortfall_kW":
                heating_load
                + cooling_load,
        }

    # Remove states that turn on an unrequested mode or omit a requested one.
    valid_pair = np.ones(
        len(
            pairs
        ),
        dtype=bool,
    )

    if heating_load > 0:
        valid_pair &= (
            pairs[
                :,
                0,
            ] > 0
        )
    else:
        valid_pair &= np.isclose(
            pairs[
                :,
                0,
            ],
            0.0,
        )

    if cooling_load > 0:
        valid_pair &= (
            pairs[
                :,
                1,
            ] > 0
        )
    else:
        valid_pair &= np.isclose(
            pairs[
                :,
                1,
            ],
            0.0,
        )

    pairs = pairs[
        valid_pair
    ]

    if len(
        pairs
    ) == 0:
        return {
            "model_status":
                "OUTSIDE_MODEL_DOMAIN",
            "total_shortfall_kW":
                heating_load
                + cooling_load,
        }

    heating_scales = np.unique(
        pairs[
            :,
            0,
        ]
    )

    cooling_scales = np.unique(
        pairs[
            :,
            1,
        ]
    )

    heating_results = mode_results_for_scales(
        circuit_model,
        "heating",
        heating_load,
        heating_scales,
        outdoor_C,
        heating_water_out_C,
        cycling_degradation_coefficient,
        frequency_step_Hz,
    )

    cooling_results = mode_results_for_scales(
        circuit_model,
        "cooling",
        cooling_load,
        cooling_scales,
        outdoor_C,
        cooling_water_out_C,
        cycling_degradation_coefficient,
        frequency_step_Hz,
    )

    heating_index = {
        round(
            float(
                scale
            ),
            6,
        ):
        index
        for index, scale
        in enumerate(
            heating_scales
        )
    }

    cooling_index = {
        round(
            float(
                scale
            ),
            6,
        ):
        index
        for index, scale
        in enumerate(
            cooling_scales
        )
    }

    h_idx = np.asarray(
        [
            heating_index[
                round(
                    float(
                        scale
                    ),
                    6,
                )
            ]
            for scale
            in pairs[
                :,
                0,
            ]
        ],
        dtype=int,
    )

    c_idx = np.asarray(
        [
            cooling_index[
                round(
                    float(
                        scale
                    ),
                    6,
                )
            ]
            for scale
            in pairs[
                :,
                1,
            ]
        ],
        dtype=int,
    )

    total_shortfall = (
        heating_results[
            "shortfall_kW"
        ][
            h_idx
        ]
        + cooling_results[
            "shortfall_kW"
        ][
            c_idx
        ]
    )

    total_power = (
        heating_results[
            "power_kW"
        ][
            h_idx
        ]
        + cooling_results[
            "power_kW"
        ][
            c_idx
        ]
    )

    finite = (
        np.isfinite(
            total_shortfall
        )
        & np.isfinite(
            total_power
        )
    )

    if not finite.any():
        return {
            "model_status":
                "OUTSIDE_MODEL_DOMAIN",
            "total_shortfall_kW":
                heating_load
                + cooling_load,
        }

    candidate_indices = np.where(
        finite
    )[0]

    order = np.lexsort(
        (
            total_power[
                candidate_indices
            ],
            np.round(
                total_shortfall[
                    candidate_indices
                ],
                6,
            ),
        )
    )

    selected_pair_index = int(
        candidate_indices[
            order[
                0
            ]
        ]
    )

    heating_scale = float(
        pairs[
            selected_pair_index,
            0,
        ]
    )

    cooling_scale = float(
        pairs[
            selected_pair_index,
            1,
        ]
    )

    hi = int(
        h_idx[
            selected_pair_index
        ]
    )

    ci = int(
        c_idx[
            selected_pair_index
        ]
    )

    short_heat = float(
        heating_results[
            "shortfall_kW"
        ][
            hi
        ]
    )

    short_cool = float(
        cooling_results[
            "shortfall_kW"
        ][
            ci
        ]
    )

    P_heat = float(
        heating_results[
            "power_kW"
        ][
            hi
        ]
    )

    P_cool = float(
        cooling_results[
            "power_kW"
        ][
            ci
        ]
    )

    candidate = {
        "model_status": "OK",
        "total_shortfall_kW": (
            short_heat
            + short_cool
        ),
        "plant_power_kW": (
            P_heat
            + P_cool
        ),
        "heating_power_kW":
            P_heat,
        "cooling_power_kW":
            P_cool,
        "heating_served_kW": (
            heating_load
            - short_heat
        ),
        "cooling_served_kW": (
            cooling_load
            - short_cool
        ),
        "thermal_shortfall_heating_kW":
            short_heat,
        "thermal_shortfall_cooling_kW":
            short_cool,
        "active_heating_circuit_scale":
            heating_scale,
        "active_cooling_circuit_scale":
            cooling_scale,
        "active_heating_circuits":
            int(
                round(
                    heating_scale
                )
            ),
        "active_cooling_circuits":
            int(
                round(
                    cooling_scale
                )
            ),
        "active_circuits_total":
            int(
                round(
                    heating_scale
                    + cooling_scale
                )
            ),
        "active_heating_units": (
            int(
                np.ceil(
                    heating_scale
                    / 2.0
                )
            )
            if heating_scale > 0
            else 0
        ),
        "active_cooling_units": (
            int(
                np.ceil(
                    cooling_scale
                    / 2.0
                )
            )
            if cooling_scale > 0
            else 0
        ),
        "heating_frequency_Hz": float(
            heating_results[
                "frequency_Hz"
            ][
                hi
            ]
        ),
        "cooling_frequency_Hz": float(
            cooling_results[
                "frequency_Hz"
            ][
                ci
            ]
        ),
        "heating_cycling": bool(
            heating_results[
                "cycling"
            ][
                hi
            ]
        ),
        "cooling_cycling": bool(
            cooling_results[
                "cycling"
            ][
                ci
            ]
        ),
        "heating_PLR_below_min": float(
            heating_results[
                "PLR"
            ][
                hi
            ]
        ),
        "cooling_PLR_below_min": float(
            cooling_results[
                "PLR"
            ][
                ci
            ]
        ),
        "heating_Qmin_kW": float(
            heating_results[
                "Qmin_kW"
            ][
                hi
            ]
        ),
        "cooling_Qmin_kW": float(
            cooling_results[
                "Qmin_kW"
            ][
                ci
            ]
        ),
        "heating_Qmax_kW": float(
            heating_results[
                "Qmax_kW"
            ][
                hi
            ]
        ),
        "cooling_Qmax_kW": float(
            cooling_results[
                "Qmax_kW"
            ][
                ci
            ]
        ),
    }

    candidate[
        "active_units_total"
    ] = (
        candidate[
            "active_heating_units"
        ]
        + candidate[
            "active_cooling_units"
        ]
    )

    return candidate


# ============================================================
# 7. THREE EXISTING FULL-SIZE HERA WRAPPER
# ============================================================

def simultaneous_three_HERA_dispatch(
    circuit_model,
    plant_module=None,
    *,
    heating_load_kW,
    cooling_load_kW,
    outdoor_C,
    heating_water_out_C,
    cooling_water_out_C,
    fan_candidates=None,
    cycling_degradation_coefficient=0.15,
    maximum_units=3,
    frequency_step_Hz=2.5,
):
    return fleet_dispatch(
        circuit_model,
        tuple(
            [1.0]
            * int(
                maximum_units
            )
        ),
        heating_load_kW,
        cooling_load_kW,
        outdoor_C,
        heating_water_out_C,
        cooling_water_out_C,
        cycling_degradation_coefficient,
        frequency_step_Hz,
    )
