"""
hera_model.py

Pure single-circuit / HERA model extracted from the former final analytical
model. This module contains no plots and does not write files.
"""

# ============================================================
# 1. IMPORTS
# ============================================================

from dataclasses import dataclass, asdict
from typing import Dict
import numpy as np


# ============================================================
# 2. DATA STRUCTURES
# ============================================================

@dataclass
class ModeCalibration:
    mode: str
    source: str
    air_UA_100_kW_K: float
    water_UA_ref_kW_K: float
    reference_air_approach_K: float
    reference_water_approach_K: float
    reference_fan_speed_fraction: float


@dataclass
class CircuitCase:
    mode: str
    outdoor_C: float
    water_out_C: float
    frequency_Hz: float
    fan_speed_fraction: float = 1.0
    air_UA_multiplier: float = 1.0
    water_UA_multiplier: float = 1.0
    water_flow_fraction: float = 1.0
    glycol_water_UA_factor: float = 1.0


# ============================================================
# 3. SINGLE-CIRCUIT MODEL
# ============================================================

class CircuitModel:
    def __init__(
        self,
        frascold_lookup,
        calibrations: Dict[str, ModeCalibration],
        fan_rated_unit_kW: float = 1.34,
        air_ht_exponent: float = 0.60,
        water_ht_exponent: float = 0.80,
        max_fan_multiplier: float = 1.30,
    ):
        self.fmap = frascold_lookup
        self.case_class = CircuitCase
        self.cal = calibrations
        self.fan_rated_unit_kW = float(fan_rated_unit_kW)
        self.fan_pair_rated_kW = self.fan_rated_unit_kW / 2.0
        self.air_ht_exponent = float(air_ht_exponent)
        self.water_ht_exponent = float(water_ht_exponent)
        self.max_fan_multiplier = float(max_fan_multiplier)
        self.min_frequency_Hz = float(np.min(self.fmap.frequencies))
        self.max_frequency_Hz = float(np.max(self.fmap.frequencies))

    def fan_power_kW(self, speed_fraction: float) -> float:
        s = float(np.clip(speed_fraction, 0.0, self.max_fan_multiplier))
        return self.fan_pair_rated_kW * s**3

    def evaluate(self, case: CircuitCase, max_iter: int = 100, tol_K: float = 1e-4) -> dict:
        if case.mode not in {"heating", "cooling"}:
            raise ValueError("mode must be heating or cooling")
        if not self.min_frequency_Hz <= case.frequency_Hz <= self.max_frequency_Hz:
            raise ValueError("frequency outside Frascold database")

        cal = self.cal[case.mode]
        UA_air = (
            cal.air_UA_100_kW_K
            * case.fan_speed_fraction**self.air_ht_exponent
            * case.air_UA_multiplier
        )
        UA_water = (
            cal.water_UA_ref_kW_K
            * case.water_UA_multiplier
            * case.water_flow_fraction**self.water_ht_exponent
            * case.glycol_water_UA_factor
        )
        if UA_air <= 0 or UA_water <= 0:
            raise ValueError("effective UA must be positive")

        if case.mode == "heating":
            T_evap = case.outdoor_C - cal.reference_air_approach_K
            T_cond = case.water_out_C + cal.reference_water_approach_K
        else:
            T_evap = case.water_out_C - cal.reference_water_approach_K
            T_cond = case.outdoor_C + cal.reference_air_approach_K

        converged = False
        for _ in range(max_iter):
            perf = self.fmap.interpolate(T_evap, T_cond, case.frequency_Hz)
            qev = float(perf["evaporator_capacity_kW"])
            qco = float(perf["condenser_capacity_kW"])
            pcomp = float(perf["compressor_power_kW"])

            if case.mode == "heating":
                qair, qwater, quseful = qev, qco, qco
                new_T_evap = case.outdoor_C - qair/UA_air
                new_T_cond = case.water_out_C + qwater/UA_water
            else:
                qair, qwater, quseful = qco, qev, qev
                new_T_evap = case.water_out_C - qwater/UA_water
                new_T_cond = case.outdoor_C + qair/UA_air

            next_evap = 0.60*T_evap + 0.40*new_T_evap
            next_cond = 0.60*T_cond + 0.40*new_T_cond
            if max(abs(next_evap-T_evap), abs(next_cond-T_cond)) < tol_K:
                T_evap, T_cond = next_evap, next_cond
                converged = True
                break
            T_evap, T_cond = next_evap, next_cond

        perf = self.fmap.interpolate(T_evap, T_cond, case.frequency_Hz)
        qev = float(perf["evaporator_capacity_kW"])
        qco = float(perf["condenser_capacity_kW"])
        pcomp = float(perf["compressor_power_kW"])
        quseful = qco if case.mode == "heating" else qev
        qair = qev if case.mode == "heating" else qco
        qwater = qco if case.mode == "heating" else qev
        pfan = self.fan_power_kW(case.fan_speed_fraction)
        pcircuit = pcomp + pfan

        return {
            **asdict(case),
            "T_evap_C": T_evap,
            "T_cond_C": T_cond,
            "temperature_lift_K": T_cond-T_evap,
            "air_approach_K": qair/UA_air,
            "water_approach_K": qwater/UA_water,
            "UA_air_effective_kW_K": UA_air,
            "UA_water_effective_kW_K": UA_water,
            "Qevap_kW": qev,
            "Qcond_kW": qco,
            "Quseful_kW": quseful,
            "Pcomp_kW": pcomp,
            "Pfan_pair_kW": pfan,
            "Pcircuit_comp_plus_fan_kW": pcircuit,
            "COP_or_EER_compressor": quseful/pcomp if pcomp > 0 else np.nan,
            "COP_or_EER_circuit": quseful/pcircuit if pcircuit > 0 else np.nan,
            "mass_flow_kg_h": float(perf.get("mass_flow_kg_h", np.nan)),
            "Tdischarge_C": float(perf.get("discharge_temperature_C", np.nan)),
            "iteration_converged": bool(converged),
            "model_status": "OK",
        }

    def safe_evaluate(self, case: CircuitCase) -> dict:
        try:
            return self.evaluate(case)
        except Exception as exc:
            return {
                **asdict(case),
                "model_status": "INVALID",
                "model_error": str(exc),
            }


    # ========================================================
    # 4. FIXED-LOAD FREQUENCY SOLVER
    # ========================================================

    def solve_frequency_for_load(
        self,
        base_case: CircuitCase,
        target_Q_kW: float,
        tolerance_percent: float = 1.0,
        iterations: int = 16,
    ) -> dict:
        """Solve compressor frequency for a fixed useful thermal duty.

        Only compressor frequency is varied. No extrapolation is allowed.
        If the duty is outside the 30...70 Hz capacity envelope, the nearest
        bound is returned with feasible=False.
        """
        target = float(target_Q_kW)

        if not np.isfinite(target) or target <= 0:
            return {
                **asdict(base_case),
                "target_Q_kW": target,
                "feasible": False,
                "model_status": "INVALID",
                "model_error": "target_Q_kW must be positive and finite",
            }

        def evaluate_at(frequency_Hz):
            case = CircuitCase(
                **{
                    **asdict(base_case),
                    "frequency_Hz": float(frequency_Hz),
                }
            )
            result = self.safe_evaluate(case)

            if result.get("model_status") != "OK":
                return None

            q = float(result.get("Quseful_kW", np.nan))
            return result if np.isfinite(q) else None

        low_frequency = self.min_frequency_Hz
        high_frequency = self.max_frequency_Hz

        low = evaluate_at(low_frequency)
        high = evaluate_at(high_frequency)

        if low is None or high is None:
            return {
                **asdict(base_case),
                "target_Q_kW": target,
                "feasible": False,
                "model_status": "INVALID",
                "model_error": "HERA model invalid at one or both frequency bounds",
            }

        q_low = float(low["Quseful_kW"])
        q_high = float(high["Quseful_kW"])

        if target <= q_low:
            best = low

        elif target >= q_high:
            best = high

        else:
            lo_f = low_frequency
            hi_f = high_frequency
            lo = low
            hi = high
            best = low

            for _ in range(int(iterations)):
                mid_f = 0.5 * (lo_f + hi_f)
                mid = evaluate_at(mid_f)

                if mid is None:
                    hi_f = mid_f
                    continue

                q_mid = float(mid["Quseful_kW"])
                best = mid

                if q_mid < target:
                    lo_f = mid_f
                    lo = mid
                else:
                    hi_f = mid_f
                    hi = mid

            best = min(
                [r for r in (lo, best, hi) if r is not None],
                key=lambda r: abs(float(r["Quseful_kW"]) - target),
            )

        result = dict(best)
        error_kW = float(result["Quseful_kW"]) - target
        error_percent = 100.0 * error_kW / target

        result["target_Q_kW"] = target
        result["capacity_error_kW"] = error_kW
        result["capacity_error_percent"] = error_percent
        result["feasible"] = bool(abs(error_percent) <= float(tolerance_percent))
        result["minimum_capacity_at_30Hz_kW"] = q_low
        result["maximum_capacity_at_70Hz_kW"] = q_high

        return result
