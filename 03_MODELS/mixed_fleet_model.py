"""
mixed_fleet_model.py

Hypothetical geometrically scaled HERA fleet wrapper.

For a unit size factor s:
    Q_small = s * Q_existing
    P_small = s * P_existing

The normalized thermodynamic map is unchanged. This is a sizing/staging
sensitivity, not a product-specific manufacturer prediction.
"""

# ============================================================
# 1. SCALED-FLEET DISPATCH
# ============================================================

def dispatch_scaled_fleet(
    annual_plant_module,
    circuit_model,
    plant_module=None,
    *,
    unit_size_factors,
    heating_load_kW,
    cooling_load_kW,
    outdoor_C,
    heating_water_out_C,
    cooling_water_out_C,
    fan_candidates=None,
    cycling_degradation_coefficient=0.15,
    frequency_step_Hz=2.5,
):
    return annual_plant_module.fleet_dispatch(
        circuit_model,
        tuple(
            float(value)
            for value in unit_size_factors
        ),
        heating_load_kW,
        cooling_load_kW,
        outdoor_C,
        heating_water_out_C,
        cooling_water_out_C,
        cycling_degradation_coefficient,
        frequency_step_Hz,
    )
