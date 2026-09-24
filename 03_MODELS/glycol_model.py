"""
glycol_model.py

Pure fluid-property model used by the thesis analyses.

This module contains no plotting and no result-file export.
"""

# ============================================================
# 1. IMPORTS
# ============================================================

from pathlib import Path
from typing import Dict, Optional, Tuple
import re
import numpy as np
import pandas as pd


# ============================================================
# 2. PURE-WATER IF97 REGION-1 CONSTANTS
# ============================================================

_IF97_R = 0.461526
_IF97_PSTAR_MPA = 16.53
_IF97_TSTAR_K = 1386.0
_WATER_PRESSURE_MPA = 0.101325

_IF97_I = np.array([
    0,0,0,0,0,0,0,0,1,1,1,1,1,1,2,2,2,2,2,3,3,3,4,4,4,5,8,8,21,23,29,30,31,32
], dtype=int)

_IF97_J = np.array([
    -2,-1,0,1,2,3,4,5,-9,-7,-1,0,1,3,-3,0,1,3,17,-4,0,6,-5,-2,10,-8,-11,-6,-29,-31,-38,-39,-40,-41
], dtype=int)

_IF97_N = np.array([
     0.14632971213167,-0.84548187169114,-0.37563603672040e1,0.33855169168385e1,
    -0.95791963387872,0.15772038513228,-0.16616417199501e-1,0.81214629983568e-3,
     0.28319080123804e-3,-0.60706301565874e-3,-0.18990068218419e-1,-0.32529748770505e-1,
    -0.21841717175414e-1,-0.52838357969930e-4,-0.47184321073267e-3,-0.30001780793026e-3,
     0.47661393906987e-4,-0.44141845330846e-5,-0.72694996297594e-15,-0.31679644845054e-4,
    -0.28270797985312e-5,-0.85205128120103e-9,-0.22425281908000e-5,-0.65171222895601e-6,
    -0.14341729937924e-12,-0.40516996860117e-6,-0.12734301741641e-8,-0.17424871230634e-9,
    -0.68762131295531e-18,0.14478307828521e-19,0.26335781662795e-22,-0.11947622640071e-22,
     0.18228094581404e-23,-0.93537087292458e-25,
], dtype=float)


# ============================================================
# 3. NUMERIC HELPERS
# ============================================================

def numeric_locale(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    s = series.astype(str).str.strip()
    s = s.replace({"": np.nan, "nan": np.nan, "None": np.nan})
    s = s.str.replace("\u00a0", "", regex=False).str.replace(" ", "", regex=False)
    s = s.str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


def _norm(name: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name).strip().lower())


# ============================================================
# 4. PURE WATER PROPERTIES
# ============================================================

def water_properties_if97(temperature_C) -> Dict[str, np.ndarray]:
    T = np.asarray(temperature_C, dtype=float)
    TK = T + 273.15
    rho = np.full(T.shape, np.nan, dtype=float)
    cp = np.full(T.shape, np.nan, dtype=float)
    valid = np.isfinite(T) & (T >= 0.0) & (T < 99.9)

    p = _WATER_PRESSURE_MPA
    pi = p / _IF97_PSTAR_MPA

    for idx in np.where(valid)[0]:
        tau = _IF97_TSTAR_K / TK[idx]
        a = 7.1 - pi
        b = tau - 1.222
        gamma_pi = 0.0
        gamma_tautau = 0.0

        for Ii, Ji, ni in zip(_IF97_I, _IF97_J, _IF97_N):
            if Ii != 0:
                gamma_pi += -ni * Ii * (a ** (Ii - 1)) * (b ** Ji)
            if Ji not in (0, 1):
                gamma_tautau += ni * Ji * (Ji - 1) * (a ** Ii) * (b ** (Ji - 2))

        v = pi * gamma_pi * _IF97_R * TK[idx] / (p * 1000.0)
        cp_i = -_IF97_R * tau**2 * gamma_tautau
        if v > 0 and cp_i > 0:
            rho[idx] = 1.0 / v
            cp[idx] = cp_i
        else:
            valid[idx] = False

    return {
        "density_kg_m3": rho,
        "cp_kJ_kgK": cp,
        "valid": valid,
    }


# ============================================================
# 5. GLYCOL PROPERTY TABLE NORMALIZATION
# ============================================================

def normalize_property_frame(dataframe: pd.DataFrame) -> Optional[pd.DataFrame]:
    d = dataframe.copy()
    normalized = {_norm(c): c for c in d.columns}

    def find(*patterns):
        for key, original in normalized.items():
            if any(pattern in key for pattern in patterns):
                return original
        return None

    tcol = find("temperaturec", "tempc", "temperature")
    rhocol = find("density", "rhokgm3")
    cpcol = find("specificheat", "cpkjkgk", "heatcapacity")
    mucol = find("viscos")
    kcol = find("thermalconduct", "conductivitywmk")

    if tcol is None or rhocol is None or cpcol is None:
        return None

    out = pd.DataFrame({
        "temperature_C": numeric_locale(d[tcol]),
        "density_kg_m3": numeric_locale(d[rhocol]),
        "cp_kJ_kgK": numeric_locale(d[cpcol]),
        "dynamic_viscosity_mPas": numeric_locale(d[mucol]) if mucol is not None else np.nan,
        "thermal_conductivity_W_mK": numeric_locale(d[kcol]) if kcol is not None else np.nan,
    })
    out = out.dropna(subset=["temperature_C", "density_kg_m3", "cp_kJ_kgK"])
    if len(out) < 2:
        return None
    return out.sort_values("temperature_C").drop_duplicates("temperature_C").reset_index(drop=True)


def concentration_from_text(text: str) -> Optional[int]:
    name = str(text).lower()
    if "water" in name:
        return 0
    match = re.search(r"(?:^|[^0-9])(0|20|25|29|30|35|40|45|50)(?:\s*%|\s*pct|\s*vol|[^0-9]|$)", name)
    return int(match.group(1)) if match else None


def load_property_workbook(path: Path) -> Dict[int, pd.DataFrame]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    tables: Dict[int, pd.DataFrame] = {}
    sheets = pd.read_excel(path, sheet_name=None, dtype=str)

    for sheet_name, frame in sheets.items():
        concentration = concentration_from_text(sheet_name)
        if concentration is None or concentration == 0:
            continue
        normalized = normalize_property_frame(frame)
        if normalized is not None:
            tables[concentration] = normalized

    return dict(sorted(tables.items()))


# ============================================================
# 6. PROPERTY INTERPOLATION
# ============================================================

def interpolate_glycol_properties(
    tables: Dict[int, pd.DataFrame],
    concentration_percent: int,
    temperature_C: float,
) -> Optional[Dict[str, float]]:
    if concentration_percent == 0:
        props = water_properties_if97(np.array([float(temperature_C)]))
        if not bool(props["valid"][0]):
            return None
        return {
            "concentration_vol_percent": 0,
            "temperature_C": float(temperature_C),
            "density_kg_m3": float(props["density_kg_m3"][0]),
            "cp_kJ_kgK": float(props["cp_kJ_kgK"][0]),
            "dynamic_viscosity_mPas": np.nan,
            "thermal_conductivity_W_mK": np.nan,
            "property_source": "IAPWS-IF97 Region 1 at 1.01325 bar",
        }

    if concentration_percent not in tables:
        return None

    d = tables[concentration_percent].copy().sort_values("temperature_C")
    x = d["temperature_C"].to_numpy(float)
    T = float(temperature_C)
    if T < x.min() or T > x.max():
        return None

    result = {
        "concentration_vol_percent": int(concentration_percent),
        "temperature_C": T,
        "property_source": "DOWCAL property workbook",
    }

    for col in [
        "density_kg_m3",
        "cp_kJ_kgK",
        "dynamic_viscosity_mPas",
        "thermal_conductivity_W_mK",
    ]:
        y = pd.to_numeric(d[col], errors="coerce").to_numpy(float)
        valid = np.isfinite(y)
        if valid.sum() < 2:
            result[col] = np.nan
        else:
            xv = x[valid]
            yv = y[valid]
            if T < xv.min() or T > xv.max():
                result[col] = np.nan
            else:
                result[col] = float(np.interp(T, xv, yv))

    result["volumetric_heat_capacity_kJ_m3K"] = (
        result["density_kg_m3"] * result["cp_kJ_kgK"]
    )
    return result


# ============================================================
# 7. RELATIVE HYDRAULIC / HX SCREENING FACTORS
# ============================================================

def relative_glycol_factors(
    tables: Dict[int, pd.DataFrame],
    concentration_percent: int,
    temperature_C: float,
    mode: str,
    reference_concentration_percent: int = 40,
    water_side_resistance_fraction: float = 0.50,
) -> Optional[Dict[str, float]]:
    p = interpolate_glycol_properties(tables, concentration_percent, temperature_C)
    ref = interpolate_glycol_properties(tables, reference_concentration_percent, temperature_C)
    if p is None or ref is None:
        return None

    needed = ["dynamic_viscosity_mPas", "thermal_conductivity_W_mK"]
    if any(not np.isfinite(p.get(k, np.nan)) or not np.isfinite(ref.get(k, np.nan)) for k in needed):
        return None

    mu = p["dynamic_viscosity_mPas"] * 1e-3
    mu_ref = ref["dynamic_viscosity_mPas"] * 1e-3
    cp = p["cp_kJ_kgK"] * 1000.0
    cp_ref = ref["cp_kJ_kgK"] * 1000.0
    k = p["thermal_conductivity_W_mK"]
    k_ref = ref["thermal_conductivity_W_mK"]
    rho = p["density_kg_m3"]
    rho_ref = ref["density_kg_m3"]

    rho_cp_ratio = p["volumetric_heat_capacity_kJ_m3K"] / ref["volumetric_heat_capacity_kJ_m3K"]
    flow_ratio = 1.0 / rho_cp_ratio
    re_ratio = (rho / rho_ref) * flow_ratio * (mu_ref / mu)
    pr = cp * mu / k
    pr_ref = cp_ref * mu_ref / k_ref
    exponent = 0.4 if mode == "heating" else 0.3
    h_ratio = (k / k_ref) * re_ratio**0.8 * (pr / pr_ref)**exponent

    rw = float(np.clip(water_side_resistance_fraction, 0.0, 1.0))
    effective_ua_ratio = 1.0 / ((1.0 - rw) + rw / h_ratio)
    dp_ratio = (rho / rho_ref) * flow_ratio**2 * re_ratio**(-0.25)
    pump_power_ratio = dp_ratio * flow_ratio

    return {
        **p,
        "mode": mode,
        "reference_concentration_vol_percent": int(reference_concentration_percent),
        "relative_rho_cp": float(rho_cp_ratio),
        "relative_volumetric_flow_same_Q_dT": float(flow_ratio),
        "relative_Re": float(re_ratio),
        "relative_Pr": float(pr / pr_ref),
        "relative_water_HTC": float(h_ratio),
        "water_side_resistance_fraction_assumed": rw,
        "relative_effective_water_HX_UA": float(effective_ua_ratio),
        "relative_pressure_drop_same_Q_dT": float(dp_ratio),
        "relative_pump_power_same_Q_dT": float(pump_power_ratio),
    }
