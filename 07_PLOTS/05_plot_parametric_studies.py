"""
05_plot_parametric_studies.py

Plots ONLY from the generated parametric result tables.
The thermodynamic model is never recalculated here.

Turn individual figures on/off in Section 3.
"""

# ============================================================
# 1. IMPORTS
# ============================================================

from pathlib import Path
import importlib.util
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm


# ============================================================
# 2. FILES USED BY THIS SCRIPT
#    CHANGE HERE IF A DIFFERENT RESULT FILE/FOLDER IS USED
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONFIG_FILE = PROJECT_ROOT / "00_CONFIG" / "config.py"
TABLE_IO_FILE = PROJECT_ROOT / "00_CONFIG" / "table_io.py"
PLOT_STYLE_FILE = PROJECT_ROOT / "00_CONFIG" / "plot_style.py"

INPUT_FOLDER = (
    PROJECT_ROOT / "06_RESULTS" / "optimization" / "parametric"
)

OUTPUT_FOLDER = (
    PROJECT_ROOT / "08_THESIS_EXPORT" / "figures" / "optimization" / "parametric"
)


# ============================================================
# 3. PLOT SELECTION
# ============================================================

PLOT_HEATING_WATER_TEMPERATURE = True
PLOT_COOLING_WATER_TEMPERATURE = True
PLOT_OUTDOOR_TEMPERATURE = True
PLOT_DIRECT_FREQUENCY = True

PLOT_AIR_UA = True
PLOT_WATER_UA = True
PLOT_FOULING = True
PLOT_FAN = True
PLOT_WATER_FLOW = True

PLOT_WATER_UA_X_FLOW = True
PLOT_AIR_UA_X_WATER_UA = True


# Restores the detailed figure set from the previous analytical model.
PLOT_LEGACY_DETAIL_SUITE = True
PLOT_GLYCOL_PERFORMANCE = True


# ============================================================
# 4. MODULE LOADING
# ============================================================

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


config = load_module("config_plot_parametric", CONFIG_FILE)
table_io = load_module("table_io_plot_parametric", TABLE_IO_FILE)
style = load_module("style_plot_parametric", PLOT_STYLE_FILE)

style.setup_plot_theme()


# ============================================================
# 5. FILE / DATA HELPERS
# ============================================================

def find_table(stem):
    xlsx = INPUT_FOLDER / f"{stem}.xlsx"
    csv = INPUT_FOLDER / f"{stem}.csv"

    if xlsx.exists():
        return xlsx

    if csv.exists():
        return csv

    return None


def read_optional(stem):
    path = find_table(stem)

    if path is None:
        return pd.DataFrame()

    return table_io.read_table(path)


def save(fig, filename, *, right=0.98):
    style.save_figure(
        fig,
        OUTPUT_FOLDER / filename,
        dpi=config.PLOT_DPI,
        right=right,
    )


def valid(data):
    if data.empty:
        return data

    q = data.copy()

    if "feasible" in q.columns:
        q = q[
            q["feasible"].astype(str).str.lower().isin(["true", "1"])
        ]

    if "model_status" in q.columns:
        q = q[
            q["model_status"].astype(str).eq("OK")
        ]

    return q


# ============================================================
# 6. 1D PLOT HELPERS
# ============================================================


def fill_missing_for_plotting(pivot):
    """Fill sparse edge/corner gaps in a 2D pivot table for plotting only."""
    filled = pivot.copy().astype(float)

    # Pass 1: interpolate along rows with endpoint extension.
    for idx in filled.index:
        row = filled.loc[idx].to_numpy(dtype=float).copy()
        x = filled.columns.to_numpy(dtype=float)
        valid = np.isfinite(row)
        if valid.sum() >= 2:
            row[~valid] = np.interp(x[~valid], x[valid], row[valid])
        filled.loc[idx] = row

    # Pass 2: interpolate along columns with endpoint extension.
    for col in filled.columns:
        col_vals = filled[col].to_numpy(dtype=float).copy()
        y = filled.index.to_numpy(dtype=float)
        valid = np.isfinite(col_vals)
        if valid.sum() >= 2:
            col_vals[~valid] = np.interp(y[~valid], y[valid], col_vals[valid])
        filled[col] = col_vals

    # Pass 3: pandas linear interpolation as a cleanup step.
    filled = filled.interpolate(axis=0, limit_direction="both")
    filled = filled.interpolate(axis=1, limit_direction="both")

    # Final fallback: nearest fill if any isolated NaN remains.
    filled = filled.ffill(axis=0).bfill(axis=0).ffill(axis=1).bfill(axis=1)

    return filled


def mode_series(
    dataframe,
    x,
    y,
    title,
    xlabel,
    ylabel,
    filename,
):
    q = valid(dataframe)

    if q.empty or y not in q.columns:
        return

    fig, ax = plt.subplots(figsize=(9.8, 5.8))

    for mode in ("heating", "cooling"):
        g = q[
            q["mode"].astype(str).str.lower().eq(mode)
        ].sort_values(x)

        if g.empty:
            continue

        ax.plot(
            g[x],
            g[y],
            marker="o",
            linewidth=2.1,
            color=style.MODE_COLOR[mode],
            label=mode.capitalize(),
        )

    style.style_axis(
        ax,
        title=title,
        xlabel=xlabel,
        ylabel=ylabel,
    )

    ax.legend(
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        borderaxespad=0.0,
    )

    save(
        fig,
        filename,
        right=0.82,
    )


def single_mode_series(
    dataframe,
    x,
    y,
    mode,
    title,
    xlabel,
    ylabel,
    filename,
):
    q = valid(dataframe)

    if q.empty or y not in q.columns:
        return

    q = q[
        q["mode"].astype(str).str.lower().eq(mode)
    ].sort_values(x)

    if q.empty:
        return

    fig, ax = plt.subplots(figsize=(9.4, 5.7))

    ax.plot(
        q[x],
        q[y],
        marker="o",
        linewidth=2.2,
        color=style.MODE_COLOR[mode],
    )

    style.style_axis(
        ax,
        title=title,
        xlabel=xlabel,
        ylabel=ylabel,
    )

    apply_ua_axis_limits(ax, x, y)

    save(
        fig,
        filename,
    )


def contour_level_spec(z_name, finite_values):
    z_key = str(z_name).lower()
    zmin = float(np.nanmin(finite_values))
    zmax = float(np.nanmax(finite_values))

    if "frequency" in z_key or z_key.endswith("_hz"):
        step = max(1, int(np.ceil((zmax - zmin) / 8.0)))
        start = int(np.floor(zmin))
        end = int(np.ceil(zmax))
        start = step * int(np.floor(start / step))
        end = step * int(np.ceil(end / step))
        if end <= start:
            end = start + step
        levels = np.arange(start, end + step, step, dtype=float)
        fmt = "%.0f"
        ticks = levels
    else:
        step = max(0.1, np.ceil(((zmax - zmin) / 8.0) * 10.0) / 10.0)
        start = np.floor(zmin / step) * step
        end = np.ceil(zmax / step) * step
        if end <= start:
            end = start + step
        levels = np.arange(start, end + 0.5 * step, step, dtype=float)
        levels = np.round(levels, 1)
        fmt = "%.1f"
        ticks = levels

    if len(levels) < 2:
        return None, None, None

    return levels, fmt, ticks


def apply_ua_axis_limits(ax, x_name, y_name):
    if str(x_name) in {"air_UA_multiplier", "water_UA_multiplier"}:
        ax.set_xlim(0.8, 1.6)
    if str(y_name) in {"air_UA_multiplier", "water_UA_multiplier"}:
        ax.set_ylim(0.8, 1.6)



# ============================================================
# 7. DISCRETE CONTOUR PLOT
# ============================================================

def colorbar_ticks_with_endpoints(levels_array, ticks_array=None):
    levels_array = np.asarray(levels_array, dtype=float)
    if ticks_array is None:
        ticks_array = np.array([], dtype=float)
    ticks_array = np.asarray(ticks_array, dtype=float)
    ticks_array = ticks_array[np.isfinite(ticks_array)]
    return np.unique(np.concatenate(([levels_array[0]], ticks_array, [levels_array[-1]])))


def contour_plot(
    dataframe,
    x,
    y,
    z,
    title,
    xlabel,
    ylabel,
    colorbar_label,
    filename,
):
    q = valid(dataframe)

    if q.empty or z not in q.columns:
        return

    pivot = q.pivot_table(
        index=y,
        columns=x,
        values=z,
        aggfunc="mean",
    ).sort_index().sort_index(axis=1)

    X, Y = np.meshgrid(
        pivot.columns.to_numpy(float),
        pivot.index.to_numpy(float),
    )

    Z_raw = pivot.to_numpy(float)
    finite_raw = Z_raw[np.isfinite(Z_raw)]

    if finite_raw.size < 3:
        return

    # Fill sparse corner/edge gaps for plotting only. The source tables remain unchanged.
    pivot_filled = fill_missing_for_plotting(pivot)
    Z_plot = pivot_filled.to_numpy(float)
    finite = Z_plot[np.isfinite(Z_plot)]

    levels, label_fmt, cbar_ticks = contour_level_spec(z, finite)

    if levels is None or np.allclose(levels[0], levels[-1]):
        return

    fig, ax = plt.subplots(figsize=(9.6, 6.2))

    norm = BoundaryNorm(
        levels,
        ncolors=256,
        clip=True,
    )

    masked = np.ma.masked_invalid(
        Z_plot
    )

    filled = ax.contourf(
        X,
        Y,
        masked,
        levels=levels,
        norm=norm,
        extend="neither",
    )

    lines = ax.contour(
        X,
        Y,
        masked,
        levels=levels,
        colors="black",
        linewidths=0.8,
    )

    ax.clabel(
        lines,
        inline=True,
        fontsize=8,
        fmt=label_fmt,
    )

    cbar = fig.colorbar(
        filled,
        ax=ax,
        extend="neither",
    )

    cbar.set_label(
        colorbar_label
    )
    cbar.set_ticks(
        colorbar_ticks_with_endpoints(levels, cbar_ticks)
    )

    style.style_axis(
        ax,
        title=title,
        xlabel=xlabel,
        ylabel=ylabel,
    )

    apply_ua_axis_limits(ax, x, y)

    save(
        fig,
        filename,
    )


# ============================================================
# 8. MAIN PLOTS
# ============================================================

def main():
    if PLOT_HEATING_WATER_TEMPERATURE:
        data = read_optional(
            "01_heating_water_temperature_fixed_load"
        )

        single_mode_series(
            data,
            "water_out_C",
            "COP_or_EER_circuit",
            "heating",
            "Heating-water temperature sensitivity at constant useful load",
            "Leaving heating-water temperature [°C]",
            "Circuit COP [-]",
            "01_heating_water_temperature_COP.png",
        )

    if PLOT_COOLING_WATER_TEMPERATURE:
        data = read_optional(
            "02_cooling_water_temperature_fixed_load"
        )

        single_mode_series(
            data,
            "water_out_C",
            "COP_or_EER_circuit",
            "cooling",
            "Cooling-water temperature sensitivity at constant useful load",
            "Leaving chilled-water temperature [°C]",
            "Circuit EER [-]",
            "02_cooling_water_temperature_EER.png",
        )

    if PLOT_OUTDOOR_TEMPERATURE:
        data = read_optional(
            "03_outdoor_temperature_fixed_load"
        )

        mode_series(
            data,
            "outdoor_C",
            "COP_or_EER_circuit",
            "Outdoor-temperature sensitivity at constant useful load",
            "Outdoor temperature [°C]",
            "Circuit COP / EER [-]",
            "03_outdoor_temperature_efficiency.png",
        )

    if PLOT_DIRECT_FREQUENCY:
        data = read_optional(
            "04_direct_compressor_frequency"
        )

        mode_series(
            data,
            "frequency_Hz",
            "COP_or_EER_circuit",
            "Compressor-frequency sensitivity",
            "Compressor frequency [Hz]",
            "Circuit COP / EER [-]",
            "04_frequency_efficiency.png",
        )

    if PLOT_AIR_UA:
        data = read_optional(
            "05_air_UA_fixed_load"
        )

        mode_series(
            data,
            "air_UA_multiplier",
            "COP_or_EER_circuit",
            "Air-side effective UA sensitivity at constant useful load",
            "Air-side effective UA multiplier [-]",
            "Circuit COP / EER [-]",
            "05_air_UA_efficiency.png",
        )

    if PLOT_WATER_UA:
        data = read_optional(
            "06_water_UA_fixed_load"
        )

        mode_series(
            data,
            "water_UA_multiplier",
            "COP_or_EER_circuit",
            "Water-side effective UA sensitivity at constant useful load",
            "Water-side effective UA multiplier [-]",
            "Circuit COP / EER [-]",
            "06_water_UA_efficiency.png",
        )

    if PLOT_FOULING:
        data = read_optional(
            "07_fouling_fixed_load"
        )

        q = valid(data)

        if not q.empty:
            fig, ax = plt.subplots(figsize=(10.0, 5.8))

            styles = {
                "air_side": "-",
                "water_side": "--",
            }

            for mode in ("heating", "cooling"):
                for location in ("air_side", "water_side"):
                    g = q[
                        q["mode"].eq(mode)
                        & q["fouling_location"].eq(location)
                    ].sort_values("UA_remaining_fraction")

                    if g.empty:
                        continue

                    ax.plot(
                        100.0 * g["UA_remaining_fraction"],
                        g["COP_or_EER_circuit"],
                        linestyle=styles[location],
                        marker="o",
                        linewidth=2.0,
                        color=style.MODE_COLOR[mode],
                        label=f"{mode.capitalize()} | {location.replace('_', ' ')}",
                    )

            style.style_axis(
                ax,
                title="HX fouling sensitivity at constant useful load",
                xlabel="Remaining effective UA [% of reference]",
                ylabel="Circuit COP / EER [-]",
            )

            ax.legend(
                loc="upper left",
                bbox_to_anchor=(1.01, 1.0),
                borderaxespad=0.0,
            )

            save(
                fig,
                "07_fouling_efficiency.png",
                right=0.78,
            )

    if PLOT_FAN:
        data = read_optional(
            "08_fan_speed_fixed_load"
        )

        mode_series(
            data,
            "fan_speed_fraction",
            "COP_or_EER_circuit",
            "Fan-speed sensitivity at constant useful load",
            "Fan-speed multiplier [-]",
            "Circuit COP / EER [-]",
            "08_fan_speed_efficiency.png",
        )

    if PLOT_WATER_FLOW:
        data = read_optional(
            "09_water_flow_and_pump_fixed_load"
        )

        mode_series(
            data,
            "water_flow_fraction",
            "COP_or_EER_with_unit_pump_screening",
            "Water-flow sensitivity including unit-pump screening",
            "Water-flow / pump-speed fraction [-]",
            "COP / EER incl. pump [-]",
            "09_water_flow_pump_efficiency.png",
        )



    if PLOT_WATER_UA_X_FLOW:
        for mode in ("heating", "cooling"):
            data = read_optional(
                f"12_{mode}_water_UA_x_flow_fixed_load"
            )

            contour_plot(
                data,
                "water_UA_multiplier",
                "water_flow_fraction",
                "COP_or_EER_with_unit_pump_screening",
                f"{mode.capitalize()}: water-side UA vs flow",
                "Water-side effective UA multiplier [-]",
                "Water-flow / pump-speed fraction [-]",
                "COP / EER incl. pump [-]",
                f"12_{mode}_water_UA_x_flow_efficiency.png",
            )

    if PLOT_AIR_UA_X_WATER_UA:
        for mode in ("heating", "cooling"):
            data = read_optional(
                f"13_{mode}_air_UA_x_water_UA_fixed_load"
            )

            contour_plot(
                data,
                "air_UA_multiplier",
                "water_UA_multiplier",
                "COP_or_EER_circuit",
                f"{mode.capitalize()}: air-side vs water-side effective UA",
                "Air-side effective UA multiplier [-]",
                "Water-side effective UA multiplier [-]",
                "Circuit COP / EER [-]",
                f"13_{mode}_air_UA_x_water_UA_efficiency.png",
            )


    # ========================================================
    # Detailed figures retained from the previous analytical
    # model so the first review contains the full information.
    # ========================================================

    if PLOT_LEGACY_DETAIL_SUITE:
        # 01/02 Heating: water temperature and outdoor condition.
        data = read_optional(
            "01_heating_water_temperature_fixed_load"
        )

        single_mode_series(
            data,
            "water_out_C",
            "frequency_Hz",
            "heating",
            "Heating-water temperature vs required compressor frequency",
            "Leaving heating-water temperature [°C]",
            "Required compressor frequency [Hz]",
            "01b_heating_water_temperature_frequency.png",
        )

        data = read_optional(
            "02_cooling_water_temperature_fixed_load"
        )

        single_mode_series(
            data,
            "water_out_C",
            "frequency_Hz",
            "cooling",
            "Cooling-water temperature vs required compressor frequency",
            "Leaving chilled-water temperature [°C]",
            "Required compressor frequency [Hz]",
            "02b_cooling_water_temperature_frequency.png",
        )

        data = read_optional(
            "03_outdoor_temperature_fixed_load"
        )

        mode_series(
            data,
            "outdoor_C",
            "frequency_Hz",
            "Outdoor temperature vs required compressor frequency",
            "Outdoor temperature [°C]",
            "Required compressor frequency [Hz]",
            "03b_outdoor_temperature_frequency.png",
        )

        # Direct compressor-frequency behaviour.
        data = read_optional(
            "04_direct_compressor_frequency"
        )

        mode_series(
            data,
            "frequency_Hz",
            "Quseful_kW",
            "Useful capacity vs compressor frequency",
            "Compressor frequency [Hz]",
            "Useful capacity [kW]",
            "04b_frequency_capacity.png",
        )

        mode_series(
            data,
            "frequency_Hz",
            "temperature_lift_K",
            "Refrigerant lift vs compressor frequency",
            "Compressor frequency [Hz]",
            "Refrigerant temperature lift [K]",
            "04c_frequency_temperature_lift.png",
        )

        # Saturation-temperature plot uses separate figures per mode to avoid
        # mixing evaporating and condensing temperature scales.
        q = valid(
            data
        )

        if not q.empty:
            for mode in (
                "heating",
                "cooling",
            ):
                g = q[
                    q[
                        "mode"
                    ].astype(str).str.lower().eq(
                        mode
                    )
                ].sort_values(
                    "frequency_Hz"
                )

                if g.empty:
                    continue

                fig, ax = plt.subplots(
                    figsize=(9.4, 5.7)
                )

                ax.plot(
                    g[
                        "frequency_Hz"
                    ],
                    g[
                        "T_evap_C"
                    ],
                    marker="o",
                    linewidth=2.0,
                    color=style.COOLING_COLOR,
                    label="Evaporating saturation",
                )

                ax.plot(
                    g[
                        "frequency_Hz"
                    ],
                    g[
                        "T_cond_C"
                    ],
                    marker="o",
                    linewidth=2.0,
                    color=style.HEATING_COLOR,
                    label="Condensing saturation",
                )

                style.style_axis(
                    ax,
                    title=f"{mode.capitalize()} saturation temperatures vs frequency",
                    xlabel="Compressor frequency [Hz]",
                    ylabel="R290 saturation temperature [°C]",
                )

                ax.legend(
                    loc="best"
                )

                save(
                    fig,
                    f"04d_{mode}_frequency_saturation_temperatures.png",
                )

        # Air-side UA: performance, frequency and approach.
        data = read_optional(
            "05_air_UA_fixed_load"
        )

        mode_series(
            data,
            "air_UA_multiplier",
            "frequency_Hz",
            "Air-side effective UA vs required compressor frequency",
            "Air-side effective UA multiplier [-]",
            "Required compressor frequency [Hz]",
            "05b_air_UA_frequency.png",
        )

        mode_series(
            data,
            "air_UA_multiplier",
            "air_approach_K",
            "Air-side effective UA vs refrigerant approach temperature",
            "Air-side effective UA multiplier [-]",
            "Air-side approach temperature [K]",
            "05c_air_UA_approach.png",
        )

        # Water-side UA.
        data = read_optional(
            "06_water_UA_fixed_load"
        )

        mode_series(
            data,
            "water_UA_multiplier",
            "frequency_Hz",
            "Water-side effective UA vs required compressor frequency",
            "Water-side effective UA multiplier [-]",
            "Required compressor frequency [Hz]",
            "06b_water_UA_frequency.png",
        )

        mode_series(
            data,
            "water_UA_multiplier",
            "water_approach_K",
            "Water-side effective UA vs refrigerant approach temperature",
            "Water-side effective UA multiplier [-]",
            "Water-side approach temperature [K]",
            "06c_water_UA_approach.png",
        )

        # Fan sensitivity.
        data = read_optional(
            "08_fan_speed_fixed_load"
        )

        mode_series(
            data,
            "fan_speed_fraction",
            "frequency_Hz",
            "Fan-speed multiplier vs required compressor frequency",
            "Fan-speed multiplier [-]",
            "Required compressor frequency [Hz]",
            "08b_fan_speed_frequency.png",
        )

        mode_series(
            data,
            "fan_speed_fraction",
            "Pfan_pair_kW",
            "Fan electrical power sensitivity",
            "Fan-speed multiplier [-]",
            "Fan-pair electrical power [kW]",
            "08c_fan_power.png",
        )

        mode_series(
            data,
            "fan_speed_fraction",
            "Pcomp_kW",
            "Fan speed effect on compressor power at constant useful duty",
            "Fan-speed multiplier [-]",
            "Compressor electrical power [kW]",
            "08d_fan_speed_compressor_power.png",
        )

        # Water flow / pump.
        data = read_optional(
            "09_water_flow_and_pump_fixed_load"
        )

        mode_series(
            data,
            "water_flow_fraction",
            "frequency_Hz",
            "Water flow vs required compressor frequency",
            "Water-flow / pump-speed fraction [-]",
            "Required compressor frequency [Hz]",
            "09b_water_flow_frequency.png",
        )

        mode_series(
            data,
            "water_flow_fraction",
            "temperature_lift_K",
            "Water flow vs refrigerant temperature lift",
            "Water-flow / pump-speed fraction [-]",
            "R290 saturation-temperature lift [K]",
            "09c_water_flow_temperature_lift.png",
        )

        mode_series(
            data,
            "water_flow_fraction",
            "screening_unit_pump_power_kW",
            "Nameplate-based unit-pump power screening",
            "Water-flow / pump-speed fraction [-]",
            "Unit-pump power [kW]",
            "09d_water_flow_pump_power.png",
        )

        # Coupled 2D frequency contours.
        for mode in (
            "heating",
            "cooling",
        ):
            data = read_optional(
                f"11_{mode}_air_UA_x_fan_fixed_load"
            )

            contour_plot(
                data,
                "air_UA_multiplier",
                "fan_speed_fraction",
                "frequency_Hz",
                f"{mode.capitalize()}: air-side UA vs fan speed — required frequency",
                "Air-side effective UA multiplier [-]",
                "Fan-speed multiplier [-]",
                "Required compressor frequency [Hz]",
                f"11_{mode}_air_UA_x_fan_frequency.png",
            )

            data = read_optional(
                f"12_{mode}_water_UA_x_flow_fixed_load"
            )

            contour_plot(
                data,
                "water_UA_multiplier",
                "water_flow_fraction",
                "frequency_Hz",
                f"{mode.capitalize()}: water-side UA vs flow — required frequency",
                "Water-side effective UA multiplier [-]",
                "Water-flow / pump-speed fraction [-]",
                "Required compressor frequency [Hz]",
                f"12_{mode}_water_UA_x_flow_frequency.png",
            )

            data = read_optional(
                f"13_{mode}_air_UA_x_water_UA_fixed_load"
            )

            contour_plot(
                data,
                "air_UA_multiplier",
                "water_UA_multiplier",
                "frequency_Hz",
                f"{mode.capitalize()}: air-side vs water-side UA — required frequency",
                "Air-side effective UA multiplier [-]",
                "Water-side effective UA multiplier [-]",
                "Required compressor frequency [Hz]",
                f"13_{mode}_air_UA_x_water_UA_frequency.png",
            )

    if PLOT_GLYCOL_PERFORMANCE:
        glycol = read_optional(
            "10b_glycol_property_based_performance"
        )

        mode_series(
            glycol,
            "concentration_vol_percent",
            "COP_or_EER_circuit",
            "Glycol concentration sensitivity",
            "Glycol concentration [vol-%]",
            "Circuit COP / EER [-]",
            "10b_glycol_efficiency.png",
        )

        mode_series(
            glycol,
            "concentration_vol_percent",
            "frequency_Hz",
            "Glycol concentration vs required compressor frequency",
            "Glycol concentration [vol-%]",
            "Required compressor frequency [Hz]",
            "10c_glycol_required_frequency.png",
        )

        mode_series(
            glycol,
            "concentration_vol_percent",
            "relative_effective_water_HX_UA",
            "Estimated effective water-HX UA effect of glycol concentration",
            "Glycol concentration [vol-%]",
            "Relative water-HX UA [-]",
            "10d_glycol_relative_effective_UA.png",
        )

        mode_series(
            glycol,
            "concentration_vol_percent",
            "relative_water_HTC",
            "Liquid-side HTC screening vs glycol concentration",
            "Glycol concentration [vol-%]",
            "Relative liquid-side HTC vs 40% [-]",
            "10e_glycol_relative_liquid_HTC.png",
        )

        mode_series(
            glycol,
            "concentration_vol_percent",
            "relative_pressure_drop_same_Q_dT",
            "Hydraulic pressure-drop screening vs glycol concentration",
            "Glycol concentration [vol-%]",
            "Relative pressure drop vs 40% [-]",
            "10f_glycol_relative_pressure_drop.png",
        )

        mode_series(
            glycol,
            "concentration_vol_percent",
            "relative_rho_cp",
            "Volumetric heat-capacity effect of glycol concentration",
            "Glycol concentration [vol-%]",
            "Relative ρcp vs 40% [-]",
            "10g_glycol_relative_rho_cp.png",
        )

        mode_series(
            glycol,
            "concentration_vol_percent",
            "COP_or_EER_with_unit_pump_screening",
            "Glycol sensitivity including unit-pump screening",
            "Glycol concentration [vol-%]",
            "COP / EER incl. pump [-]",
            "10h_glycol_efficiency_with_pump.png",
        )


    pass


if __name__ == "__main__":
    main()
