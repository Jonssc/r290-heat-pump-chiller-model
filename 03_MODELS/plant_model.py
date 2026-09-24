"""
plant_model.py

Reusable plant-level control and hydraulic screening functions.

This module:
- does not read files;
- does not write files;
- does not create plots.

It is built on top of ``hera_model.CircuitModel`` and provides:
- one- versus two-circuit unit operation;
- second-circuit staging strategy curves;
- 1/2/3-HERA plant dispatch;
- optional per-unit pump-power screening;
- ideal buffer-tank cycling sensitivity.

C1/C2 physical identities are deliberately not used as staging labels. The
plant model refers to "one active circuit" and "two active circuits".
"""

# ============================================================
# 1. IMPORTS
# ============================================================

from __future__ import annotations

from itertools import combinations_with_replacement
from typing import Iterable, Optional

import numpy as np
import pandas as pd


# ============================================================
# 2. PUMP SCREENING
# ============================================================

def unit_pump_power_kW(
    speed_fraction: float,
    electrical_reference_kW: float,
    *,
    pressure_drop_factor: float = 1.0,
    motor_load_factor: float = 1.0,
    power_exponent: float = 3.0,
) -> float:
    """Nameplate-based variable-speed pump screening.

    This is not measured pump input. The reference is normally P2/PDS
    efficiency for the identified MGE90LC family.
    """
    speed = max(float(speed_fraction), 0.0)
    return float(
        electrical_reference_kW
        * motor_load_factor
        * pressure_drop_factor
        * speed**power_exponent
    )


# ============================================================
# 3. UNIT OPERATION
# ============================================================

def best_unit_operation_fixed_circuits(
    circuit_model,
    mode: str,
    unit_load_kW: float,
    outdoor_C: float,
    water_out_C: float,
    active_circuits: int,
    fan_candidates: Iterable[float],
    *,
    include_unit_pump: bool = False,
    pump_speed_fraction: float = 1.0,
    pump_electrical_reference_kW: float = 0.0,
    pump_pressure_drop_factor: float = 1.0,
    pump_motor_load_factor: float = 1.0,
    pump_power_exponent: float = 3.0,
    water_flow_fraction: float = 1.0,
    air_UA_multiplier: float = 1.0,
    water_UA_multiplier: float = 1.0,
    glycol_water_UA_factor: float = 1.0,
    frequency_seed_Hz: float = 50.0,
) -> Optional[dict]:
    if unit_load_kW <= 0:
        return {
            "mode": mode,
            "unit_load_kW": 0.0,
            "active_circuits": 0,
            "frequency_Hz": 0.0,
            "fan_speed_fraction": 0.0,
            "unit_chiller_power_kW": 0.0,
            "unit_pump_power_kW": 0.0,
            "unit_total_power_kW": 0.0,
            "unit_COP_or_EER": np.nan,
            "feasible": True,
        }

    n = int(active_circuits)
    if n not in (1, 2):
        raise ValueError("active_circuits must be 1 or 2")

    required_per_circuit = float(unit_load_kW) / n
    best = None

    for fan_speed in fan_candidates:
        base_case = circuit_model.case_class(
            mode=mode,
            outdoor_C=float(outdoor_C),
            water_out_C=float(water_out_C),
            frequency_Hz=float(frequency_seed_Hz),
            fan_speed_fraction=float(fan_speed),
            air_UA_multiplier=float(air_UA_multiplier),
            water_UA_multiplier=float(water_UA_multiplier),
            water_flow_fraction=float(water_flow_fraction),
            glycol_water_UA_factor=float(glycol_water_UA_factor),
        )

        result = circuit_model.solve_frequency_for_load(
            base_case,
            required_per_circuit,
        )

        if not bool(result.get("feasible", False)):
            continue

        chiller_power = (
            n
            * float(result["Pcircuit_comp_plus_fan_kW"])
        )

        pump_power = (
            unit_pump_power_kW(
                pump_speed_fraction,
                pump_electrical_reference_kW,
                pressure_drop_factor=pump_pressure_drop_factor,
                motor_load_factor=pump_motor_load_factor,
                power_exponent=pump_power_exponent,
            )
            if include_unit_pump
            else 0.0
        )

        total_power = chiller_power + pump_power

        candidate = {
            "mode": mode,
            "unit_load_kW": float(unit_load_kW),
            "active_circuits": n,
            "frequency_Hz": float(result["frequency_Hz"]),
            "fan_speed_fraction": float(fan_speed),
            "unit_chiller_power_kW": float(chiller_power),
            "unit_pump_power_kW": float(pump_power),
            "unit_total_power_kW": float(total_power),
            "unit_COP_or_EER": (
                float(unit_load_kW) / total_power
                if total_power > 0
                else np.nan
            ),
            "T_evap_C": float(result.get("T_evap_C", np.nan)),
            "T_cond_C": float(result.get("T_cond_C", np.nan)),
            "temperature_lift_K": float(result.get("temperature_lift_K", np.nan)),
            "air_approach_K": float(result.get("air_approach_K", np.nan)),
            "water_approach_K": float(result.get("water_approach_K", np.nan)),
            "feasible": True,
        }

        if (
            best is None
            or candidate["unit_total_power_kW"]
            < best["unit_total_power_kW"]
        ):
            best = candidate

    return best


def best_unit_operation(
    circuit_model,
    mode: str,
    unit_load_kW: float,
    outdoor_C: float,
    water_out_C: float,
    fan_candidates: Iterable[float],
    **kwargs,
) -> Optional[dict]:
    best = None

    for n in (1, 2):
        candidate = best_unit_operation_fixed_circuits(
            circuit_model,
            mode,
            unit_load_kW,
            outdoor_C,
            water_out_C,
            n,
            fan_candidates,
            **kwargs,
        )

        if candidate is None:
            continue

        if (
            best is None
            or candidate["unit_total_power_kW"]
            < best["unit_total_power_kW"]
        ):
            best = candidate

    return best


# ============================================================
# 4. UNIT CONFIGURATION CURVES
# ============================================================

def build_unit_configuration_table(
    circuit_model,
    mode: str,
    outdoor_C: float,
    water_out_C: float,
    load_values_kW: Iterable[float],
    fan_candidates: Iterable[float],
    **kwargs,
) -> pd.DataFrame:
    rows = []

    for load in load_values_kW:
        for n in (1, 2):
            row = best_unit_operation_fixed_circuits(
                circuit_model,
                mode,
                float(load),
                outdoor_C,
                water_out_C,
                n,
                fan_candidates,
                **kwargs,
            )

            if row is not None:
                rows.append(row)

    return pd.DataFrame(rows)


def select_best_unit_envelope(configuration_table: pd.DataFrame) -> pd.DataFrame:
    if configuration_table.empty:
        return pd.DataFrame()

    rows = []

    for load, group in configuration_table.groupby("unit_load_kW"):
        q = group.dropna(subset=["unit_total_power_kW"])
        if q.empty:
            continue
        rows.append(
            q.loc[q["unit_total_power_kW"].idxmin()].to_dict()
        )

    return pd.DataFrame(rows).sort_values("unit_load_kW").reset_index(drop=True)


def first_lower_power_load(
    configuration_table: pd.DataFrame,
    *,
    challenger: int = 2,
    incumbent: int = 1,
    minimum_advantage_kW: float = 0.10,
) -> Optional[float]:
    if configuration_table.empty:
        return None

    a = configuration_table[
        configuration_table["active_circuits"] == incumbent
    ][["unit_load_kW", "unit_total_power_kW"]].rename(
        columns={"unit_total_power_kW": "incumbent_power_kW"}
    )

    b = configuration_table[
        configuration_table["active_circuits"] == challenger
    ][["unit_load_kW", "unit_total_power_kW"]].rename(
        columns={"unit_total_power_kW": "challenger_power_kW"}
    )

    merged = a.merge(b, on="unit_load_kW", how="inner")
    if merged.empty:
        return None

    better = merged[
        (
            merged["incumbent_power_kW"]
            - merged["challenger_power_kW"]
        )
        > float(minimum_advantage_kW)
    ]

    if better.empty:
        return None

    return float(better["unit_load_kW"].min())


def build_switch_strategy_curve(
    configuration_table: pd.DataFrame,
    switch_load_kW: Optional[float],
) -> pd.DataFrame:
    """Build a delayed or prescribed 1->2 active-circuit strategy."""
    if configuration_table.empty:
        return pd.DataFrame()

    one = configuration_table[
        configuration_table["active_circuits"] == 1
    ].copy()

    two = configuration_table[
        configuration_table["active_circuits"] == 2
    ].copy()

    if one.empty and two.empty:
        return pd.DataFrame()

    loads = sorted(
        set(
            pd.to_numeric(
                configuration_table["unit_load_kW"],
                errors="coerce",
            ).dropna().astype(float)
        )
    )

    delayed = switch_load_kW is None
    max_one = (
        float(one["unit_load_kW"].max())
        if not one.empty
        else -np.inf
    )

    rows = []

    for load in loads:
        r1 = one[np.isclose(one["unit_load_kW"], load)]
        r2 = two[np.isclose(two["unit_load_kW"], load)]

        choice = None

        if delayed:
            if load <= max_one and not r1.empty:
                choice = r1.iloc[0]
            elif not r2.empty:
                choice = r2.iloc[0]
            elif not r1.empty:
                choice = r1.iloc[0]

        else:
            if load < float(switch_load_kW):
                if not r1.empty:
                    choice = r1.iloc[0]
                elif not r2.empty:
                    choice = r2.iloc[0]
            else:
                if not r2.empty:
                    choice = r2.iloc[0]
                elif not r1.empty:
                    choice = r1.iloc[0]

        if choice is not None:
            row = dict(choice)
            row["strategy_type"] = (
                "delayed_capacity_limited_reference"
                if delayed
                else "efficiency_based_second_circuit_switch"
            )
            row["strategy_switch_load_kW"] = (
                np.nan
                if delayed
                else float(switch_load_kW)
            )
            rows.append(row)

    return pd.DataFrame(rows)


# ============================================================
# 5. 1 / 2 / 3 HERA DISPATCH FROM UNIT TABLE
# ============================================================

def exact_n_unit_dispatch_from_unit_table(
    unit_best_table: pd.DataFrame,
    *,
    n_units: int,
    load_step_kW: float = 5.0,
) -> pd.DataFrame:
    """Minimum-power dispatch using exactly ``n_units`` active identical HERAs.

    The unit table must already contain the minimum-power operating point for
    one HERA at every discretized unit load.  This function then optimizes the
    *distribution* of a requested plant load between exactly 1, 2 or 3 active
    physical units.  Equal loading is therefore not imposed.

    Example: for a 180 kW plant load with three active units, 60/60/60 kW is
    evaluated, but so are 50/60/70 kW and every other combination available on
    the discrete load grid.  The combination with the lowest summed electrical
    power is retained.
    """
    if unit_best_table.empty:
        return pd.DataFrame()

    n_units = int(n_units)
    if n_units < 1:
        raise ValueError("n_units must be >= 1")

    step = float(load_step_kW)
    if step <= 0:
        raise ValueError("load_step_kW must be > 0")

    table = unit_best_table.copy()
    table["unit_load_kW"] = pd.to_numeric(
        table["unit_load_kW"], errors="coerce"
    )
    table["unit_total_power_kW"] = pd.to_numeric(
        table["unit_total_power_kW"], errors="coerce"
    )
    table = table.dropna(
        subset=["unit_load_kW", "unit_total_power_kW"]
    )
    table = table[
        (table["unit_load_kW"] > 0)
        & (table["unit_total_power_kW"] > 0)
    ].copy()

    if table.empty:
        return pd.DataFrame()

    # One reusable operating point per discrete unit-load index.  If rounding
    # ever creates duplicates, retain the lower-power point.
    options = {}
    for _, row in table.iterrows():
        idx = int(round(float(row["unit_load_kW"]) / step))
        if idx <= 0:
            continue
        record = row.to_dict()
        previous = options.get(idx)
        if (
            previous is None
            or float(record["unit_total_power_kW"])
            < float(previous["unit_total_power_kW"])
        ):
            options[idx] = record

    if not options:
        return pd.DataFrame()

    # Dynamic programming: after each iteration, ``states[total_idx]`` stores
    # the lowest-power way of supplying that total load with exactly the number
    # of units processed so far.  No zero-load option is included, so every
    # unit in the final allocation is genuinely active.
    states = {0: (0.0, [])}

    for _ in range(n_units):
        next_states = {}
        for previous_idx, (previous_power, previous_alloc) in states.items():
            for unit_idx, operating_point in options.items():
                total_idx = previous_idx + unit_idx
                total_power = (
                    previous_power
                    + float(operating_point["unit_total_power_kW"])
                )

                current = next_states.get(total_idx)
                if current is None or total_power < current[0]:
                    next_states[total_idx] = (
                        total_power,
                        previous_alloc + [operating_point],
                    )

        states = next_states
        if not states:
            return pd.DataFrame()

    rows = []

    for total_idx, (total_power, allocation) in sorted(states.items()):
        total_load = total_idx * step
        allocation = sorted(
            allocation,
            key=lambda r: float(r.get("unit_load_kW", 0.0)),
        )

        plant_chiller_power = sum(
            float(r.get("unit_chiller_power_kW", 0.0))
            for r in allocation
        )
        plant_pump_power = sum(
            float(r.get("unit_pump_power_kW", 0.0))
            for r in allocation
        )

        rows.append({
            "total_load_kW": float(total_load),
            "active_units": n_units,
            "plant_power_kW": float(total_power),
            "plant_COP_or_EER": (
                float(total_load) / float(total_power)
                if total_power > 0
                else np.nan
            ),
            "unit_loads_kW": "; ".join(
                f"{float(r['unit_load_kW']):.1f}"
                for r in allocation
            ),
            "circuits_per_unit": "; ".join(
                str(int(r.get("active_circuits", 0)))
                for r in allocation
            ),
            "frequencies_Hz": "; ".join(
                f"{float(r.get('frequency_Hz', np.nan)):.1f}"
                for r in allocation
            ),
            "fan_speed_fractions": "; ".join(
                f"{float(r.get('fan_speed_fraction', np.nan)):.2f}"
                for r in allocation
            ),
            "plant_chiller_power_kW": float(plant_chiller_power),
            "plant_pump_power_kW": float(plant_pump_power),
            "load_split_optimized": True,
        })

    return pd.DataFrame(rows)


def selected_exact_dispatch_envelope(
    exact_dispatch_tables: dict[int, pd.DataFrame],
) -> pd.DataFrame:
    """Select the minimum-power exact-N alternative at every common plant load."""
    frames = []

    for n_units, table in exact_dispatch_tables.items():
        if table is None or table.empty:
            continue
        q = table.copy()
        q["active_units"] = int(n_units)
        frames.append(q)

    if not frames:
        return pd.DataFrame()

    all_options = pd.concat(frames, ignore_index=True)
    all_options["plant_power_kW"] = pd.to_numeric(
        all_options["plant_power_kW"], errors="coerce"
    )
    all_options["total_load_kW"] = pd.to_numeric(
        all_options["total_load_kW"], errors="coerce"
    )
    all_options = all_options.dropna(
        subset=["plant_power_kW", "total_load_kW"]
    )

    rows = []
    for load, group in all_options.groupby("total_load_kW", sort=True):
        best = group.loc[group["plant_power_kW"].idxmin()].copy()
        best["selected_from_exact_unit_curves"] = True
        rows.append(best.to_dict())

    if not rows:
        return pd.DataFrame()

    return (
        pd.DataFrame(rows)
        .sort_values("total_load_kW")
        .reset_index(drop=True)
    )

def plant_dispatch_from_unit_table(
    unit_best_table: pd.DataFrame,
    *,
    max_units: int = 3,
    load_step_kW: float = 5.0,
) -> pd.DataFrame:
    """Find the lowest-power allocation among up to ``max_units`` identical HERAs.

    The thermodynamic model is not recalculated here. The function reuses a
    precomputed best-unit table, which is the intended V2 architecture.
    """
    if unit_best_table.empty:
        return pd.DataFrame()

    table = unit_best_table.copy()
    table = table[table["unit_load_kW"] > 0].sort_values("unit_load_kW")

    options = [
        {
            "unit_load_kW": 0.0,
            "active_circuits": 0,
            "frequency_Hz": 0.0,
            "fan_speed_fraction": 0.0,
            "unit_chiller_power_kW": 0.0,
            "unit_pump_power_kW": 0.0,
            "unit_total_power_kW": 0.0,
        }
    ] + table.to_dict("records")

    best_by_load = {}

    for combination in combinations_with_replacement(
        range(len(options)),
        int(max_units),
    ):
        chosen = [options[i] for i in combination]

        total_load = sum(float(r["unit_load_kW"]) for r in chosen)
        if total_load <= 0:
            continue

        rounded_load = round(total_load / load_step_kW) * load_step_kW

        total_power = sum(float(r["unit_total_power_kW"]) for r in chosen)
        active = [r for r in chosen if float(r["unit_load_kW"]) > 0]

        candidate = {
            "total_load_kW": float(rounded_load),
            "optimal_active_units": len(active),
            "plant_power_kW": float(total_power),
            "plant_COP_or_EER": (
                rounded_load / total_power
                if total_power > 0
                else np.nan
            ),
            "unit_loads_kW": "; ".join(
                f"{float(r['unit_load_kW']):.1f}"
                for r in active
            ),
            "circuits_per_unit": "; ".join(
                str(int(r["active_circuits"]))
                for r in active
            ),
            "frequencies_Hz": "; ".join(
                f"{float(r['frequency_Hz']):.1f}"
                for r in active
            ),
            "fan_speed_fractions": "; ".join(
                f"{float(r['fan_speed_fraction']):.2f}"
                for r in active
            ),
            "plant_chiller_power_kW": sum(
                float(r.get("unit_chiller_power_kW", 0.0))
                for r in active
            ),
            "plant_pump_power_kW": sum(
                float(r.get("unit_pump_power_kW", 0.0))
                for r in active
            ),
        }

        previous = best_by_load.get(rounded_load)

        if (
            previous is None
            or candidate["plant_power_kW"]
            < previous["plant_power_kW"]
        ):
            best_by_load[rounded_load] = candidate

    return (
        pd.DataFrame(best_by_load.values())
        .sort_values("total_load_kW")
        .reset_index(drop=True)
    )


# ============================================================
# 6. IDEAL BUFFER CYCLING
# ============================================================

def ideal_buffer_cycle(
    *,
    minimum_heat_pump_capacity_kW: float,
    average_building_load_kW: float,
    volume_L: float,
    deadband_K: float,
    density_kg_m3: float = 1000.0,
    cp_kJ_kgK: float = 4.18,
) -> dict:
    """Ideal lossless buffer cycling below minimum steady HP capacity."""
    q_min = float(minimum_heat_pump_capacity_kW)
    q_load = float(average_building_load_kW)

    energy_kWh = (
        float(volume_L) / 1000.0
        * float(density_kg_m3)
        * float(cp_kJ_kgK)
        * float(deadband_K)
        / 3600.0
    )

    result = {
        "minimum_heat_pump_capacity_kW": q_min,
        "average_building_load_kW": q_load,
        "load_fraction_of_Qmin": (
            q_load / q_min if q_min > 0 else np.nan
        ),
        "buffer_volume_L": float(volume_L),
        "deadband_K": float(deadband_K),
        "usable_buffer_energy_kWh": energy_kWh,
    }

    if q_min <= 0 or q_load <= 0 or q_load >= q_min:
        result.update({
            "charging_time_min": np.nan,
            "discharging_time_min": np.nan,
            "cycle_time_min": np.nan,
            "starts_per_day": (
                0.0 if q_load >= q_min else np.nan
            ),
            "heat_pump_runtime_per_cycle_min": np.nan,
            "heat_pump_runtime_hours_per_day": (
                24.0 if q_load >= q_min else 0.0
            ),
        })
        return result

    charge_rate = q_min - q_load
    discharge_rate = q_load

    charge_h = energy_kWh / charge_rate
    discharge_h = energy_kWh / discharge_rate
    cycle_h = charge_h + discharge_h

    result.update({
        "charging_time_min": 60.0 * charge_h,
        "discharging_time_min": 60.0 * discharge_h,
        "cycle_time_min": 60.0 * cycle_h,
        "starts_per_day": 24.0 / cycle_h,
        "heat_pump_runtime_per_cycle_min": 60.0 * charge_h,
        "heat_pump_runtime_hours_per_day": (
            24.0 * q_load / q_min
        ),
    })

    return result
