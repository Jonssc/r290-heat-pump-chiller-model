"""
frascold_grid_model.py

Reusable lookup/interpolation model for the generated Frascold master database.
This lets Validation and HERA analyses reuse the calculated database instead of
re-reading/recalculating the original compressor workbook.
"""

# ============================================================
# 1. IMPORTS
# ============================================================

from pathlib import Path
import numpy as np
import pandas as pd


# ============================================================
# 2. GRID LOOKUP MODEL
# ============================================================

class FrascoldGridLookup:
    def __init__(self, table_path: Path):
        table_path = Path(table_path)
        if not table_path.exists():
            raise FileNotFoundError(table_path)

        if table_path.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
            d = pd.read_excel(table_path)
        else:
            d = pd.read_csv(table_path, sep=None, engine="python", decimal=",")

        required = {"T_evap_C", "T_cond_C", "frequency_Hz", "model_status"}
        missing = required - set(d.columns)
        if missing:
            raise KeyError(f"Frascold grid is missing columns: {sorted(missing)}")

        d = d[d["model_status"].astype(str).eq("OK")].copy()
        for col in d.columns:
            if col not in {"model_status", "error_type"}:
                d[col] = pd.to_numeric(d[col], errors="coerce")

        self.data = d
        self.frequencies = np.sort(d["frequency_Hz"].dropna().unique().astype(float))
        self.tevaps = np.sort(d["T_evap_C"].dropna().unique().astype(float))
        self.tconds = np.sort(d["T_cond_C"].dropna().unique().astype(float))

        self._rows = {
            (float(r.frequency_Hz), float(r.T_evap_C), float(r.T_cond_C)): r
            for r in d.itertuples(index=False)
        }

    @staticmethod
    def _bracket(axis: np.ndarray, value: float, name: str):
        x = float(value)
        if not np.isfinite(x):
            raise ValueError(f"{name} is not finite")
        if x < axis[0] or x > axis[-1]:
            raise ValueError(f"{name}={x:.3f} outside [{axis[0]:g}, {axis[-1]:g}]")
        exact = np.where(np.isclose(axis, x, atol=1e-9, rtol=0))[0]
        if len(exact):
            a = float(axis[exact[0]])
            return a, a, 0.0
        hi = int(np.searchsorted(axis, x, side="right"))
        lo = hi - 1
        a, b = float(axis[lo]), float(axis[hi])
        return a, b, float((x-a)/(b-a))

    @staticmethod
    def _choices(lo, hi, weight_hi):
        if lo == hi:
            return [(lo, 1.0)]
        return [(lo, 1.0-weight_hi), (hi, weight_hi)]

    def interpolate(self, T_evap_C: float, T_cond_C: float, frequency_Hz: float) -> dict:
        f0, f1, wf = self._bracket(self.frequencies, frequency_Hz, "frequency_Hz")
        e0, e1, we = self._bracket(self.tevaps, T_evap_C, "T_evap_C")
        c0, c1, wc = self._bracket(self.tconds, T_cond_C, "T_cond_C")

        weighted = []
        missing = []
        for f, fw in self._choices(f0, f1, wf):
            for te, ew in self._choices(e0, e1, we):
                for tc, cw in self._choices(c0, c1, wc):
                    row = self._rows.get((f, te, tc))
                    if row is None:
                        missing.append((f, te, tc))
                    else:
                        weighted.append((fw*ew*cw, row))

        if missing:
            raise ValueError("Interpolation touches an invalid Frascold grid cell")

        fields = [
            "evaporator_capacity_kW",
            "condenser_capacity_kW",
            "compressor_power_kW",
            "cooling_EER",
            "heating_COP",
            "current_A",
            "mass_flow_kg_h",
            "discharge_temperature_C",
        ]
        out = {
            "T_evap_C": float(T_evap_C),
            "T_cond_C": float(T_cond_C),
            "frequency_Hz": float(frequency_Hz),
        }
        for field in fields:
            values = []
            for weight, row in weighted:
                value = getattr(row, field, np.nan)
                values.append((weight, float(value) if pd.notna(value) else np.nan))
            out[field] = (
                float(sum(w*v for w,v in values))
                if all(np.isfinite(v) for _,v in values)
                else np.nan
            )
        return out
