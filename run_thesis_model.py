"""
run_thesis_model.py

Master runner for the reorganized thesis project.
Set only the tasks you want to run to True.
"""

from pathlib import Path
import subprocess
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parent

SCRIPTS = {
    "frascold_database": PROJECT_ROOT/"04_GENERATE_DATABASES"/"01_generate_frascold_grid.py",
    "glycol_database": PROJECT_ROOT/"04_GENERATE_DATABASES"/"02_generate_glycol_database.py",
    "glycol_meter_validation": PROJECT_ROOT/"05_ANALYSIS"/"01_glycol_meter_validation.py",
    "kiona_clean": PROJECT_ROOT/"05_ANALYSIS"/"02_clean_kiona_detailed.py",
    "kiona_filter": PROJECT_ROOT/"05_ANALYSIS"/"03_filter_kiona_stable_periods.py",
    "validation": PROJECT_ROOT/"05_ANALYSIS"/"04_validate_kiona_frascold.py",
    "hx_calibration": PROJECT_ROOT/"05_ANALYSIS"/"05_calibrate_hera_hx.py",
    "parametric_analysis": PROJECT_ROOT/"05_ANALYSIS"/"06_generate_parametric_studies.py",
    "dispatch_analysis": PROJECT_ROOT/"05_ANALYSIS"/"07_generate_circuit_and_plant_dispatch.py",
    "buffer_analysis": PROJECT_ROOT/"05_ANALYSIS"/"08_generate_buffer_cycling.py",
    "actual_staging": PROJECT_ROOT/"05_ANALYSIS"/"09_actual_circuit_staging.py",
    "carnot_analysis": PROJECT_ROOT/"05_ANALYSIS"/"10_carnot_second_law.py",
    "standard_seasonal": PROJECT_ROOT/"05_ANALYSIS"/"11_standardized_SCOP_SEER.py",
    "annual_clean": PROJECT_ROOT/"05_ANALYSIS"/"12_clean_kiona_annual.py",
    "annual_load_analysis": PROJECT_ROOT/"05_ANALYSIS"/"13_annual_load_analysis.py",
    "hybrid_analysis": PROJECT_ROOT/"05_ANALYSIS"/"14_hybrid_operation.py",
    "annual_plant_analysis": PROJECT_ROOT/"05_ANALYSIS"/"15_annual_reconstruction_and_plant.py",
    "heat_recovery_analysis": PROJECT_ROOT/"05_ANALYSIS"/"16_hybrid_water_water_heat_recovery.py",
    "mixed_sizing_analysis": PROJECT_ROOT/"05_ANALYSIS"/"17_mixed_unit_sizing.py",
    "hybrid_detailed_analysis": PROJECT_ROOT/"05_ANALYSIS"/"18_hybrid_detailed_efficiency.py",
    "system_performance_map_analysis": PROJECT_ROOT/"05_ANALYSIS"/"19_generate_system_performance_maps.py",
    "frascold_plots": PROJECT_ROOT/"07_PLOTS"/"01_plot_frascold.py",
    "glycol_plots": PROJECT_ROOT/"07_PLOTS"/"02_plot_glycol.py",
    "kiona_plots": PROJECT_ROOT/"07_PLOTS"/"03_plot_kiona_filter.py",
    "validation_plots": PROJECT_ROOT/"07_PLOTS"/"04_plot_validation.py",
    "parametric_plots": PROJECT_ROOT/"07_PLOTS"/"05_plot_parametric_studies.py",
    "dispatch_plots": PROJECT_ROOT/"07_PLOTS"/"06_plot_circuit_and_plant_dispatch.py",
    "buffer_plots": PROJECT_ROOT/"07_PLOTS"/"07_plot_buffer_cycling.py",
    "actual_staging_plots": PROJECT_ROOT/"07_PLOTS"/"08_plot_actual_circuit_staging.py",
    "carnot_plots": PROJECT_ROOT/"07_PLOTS"/"09_plot_carnot_second_law.py",
    "standard_seasonal_plots": PROJECT_ROOT/"07_PLOTS"/"10_plot_standardized_SCOP_SEER.py",
    "annual_load_plots": PROJECT_ROOT/"07_PLOTS"/"11_plot_annual_load.py",
    "hybrid_plots": PROJECT_ROOT/"07_PLOTS"/"12_plot_hybrid_operation.py",
    "annual_plant_plots": PROJECT_ROOT/"07_PLOTS"/"13_plot_annual_plant.py",
    "heat_recovery_plots": PROJECT_ROOT/"07_PLOTS"/"14_plot_heat_recovery.py",
    "mixed_sizing_plots": PROJECT_ROOT/"07_PLOTS"/"15_plot_mixed_unit_sizing.py",
    "optimization_summary_plots": PROJECT_ROOT/"07_PLOTS"/"16_plot_optimization_summary.py",
    "hybrid_detailed_plots": PROJECT_ROOT/"07_PLOTS"/"17_plot_hybrid_detailed_efficiency.py",
    "system_performance_map_plots": PROJECT_ROOT/"07_PLOTS"/"18_plot_system_performance_maps.py",
}

RUN_COMPLETE_PIPELINE_ONCE = True
RUN_ALL_PLOTS_ONLY_ONCE = False

RUN_FRASCOLD_DATABASE = False
RUN_GLYCOL_DATABASE = False
RUN_GLYCOL_METER_VALIDATION = False
RUN_KIONA_CLEANING = False
RUN_KIONA_FILTER = False
RUN_VALIDATION = False
RUN_HX_CALIBRATION = False
RUN_PARAMETRIC_ANALYSIS = False
RUN_DISPATCH_ANALYSIS = False
RUN_BUFFER_ANALYSIS = False
RUN_ACTUAL_STAGING = False
RUN_CARNOT_ANALYSIS = False
RUN_STANDARD_SEASONAL = False
RUN_ANNUAL_CLEAN = False
RUN_ANNUAL_LOAD_ANALYSIS = False
RUN_HYBRID_ANALYSIS = False
RUN_HYBRID_DETAILED_ANALYSIS = False
RUN_ANNUAL_PLANT_ANALYSIS = False
RUN_HEAT_RECOVERY_ANALYSIS = False
RUN_MIXED_SIZING_ANALYSIS = False
RUN_SYSTEM_PERFORMANCE_MAP_ANALYSIS = False
RUN_FRASCOLD_PLOTS = False
RUN_GLYCOL_PLOTS = False
RUN_KIONA_PLOTS = False
RUN_VALIDATION_PLOTS = False
RUN_PARAMETRIC_PLOTS = False
RUN_DISPATCH_PLOTS = False
RUN_BUFFER_PLOTS = False
RUN_ACTUAL_STAGING_PLOTS = False
RUN_CARNOT_PLOTS = False
RUN_STANDARD_SEASONAL_PLOTS = False
RUN_ANNUAL_LOAD_PLOTS = False
RUN_HYBRID_PLOTS = False
RUN_HYBRID_DETAILED_PLOTS = False
RUN_ANNUAL_PLANT_PLOTS = False
RUN_HEAT_RECOVERY_PLOTS = False
RUN_MIXED_SIZING_PLOTS = False
RUN_OPTIMIZATION_SUMMARY_PLOTS = False
RUN_SYSTEM_PERFORMANCE_MAP_PLOTS = False

TASKS = [
    (RUN_FRASCOLD_DATABASE, "frascold_database"),
    (RUN_GLYCOL_DATABASE, "glycol_database"),
    (RUN_GLYCOL_METER_VALIDATION, "glycol_meter_validation"),
    (RUN_KIONA_CLEANING, "kiona_clean"),
    (RUN_KIONA_FILTER, "kiona_filter"),
    (RUN_VALIDATION, "validation"),
    (RUN_HX_CALIBRATION, "hx_calibration"),
    (RUN_PARAMETRIC_ANALYSIS, "parametric_analysis"),
    (RUN_DISPATCH_ANALYSIS, "dispatch_analysis"),
    (RUN_BUFFER_ANALYSIS, "buffer_analysis"),
    (RUN_ACTUAL_STAGING, "actual_staging"),
    (RUN_CARNOT_ANALYSIS, "carnot_analysis"),
    (RUN_STANDARD_SEASONAL, "standard_seasonal"),
    (RUN_ANNUAL_CLEAN, "annual_clean"),
    (RUN_ANNUAL_LOAD_ANALYSIS, "annual_load_analysis"),
    (RUN_HYBRID_ANALYSIS, "hybrid_analysis"),
    (RUN_HYBRID_DETAILED_ANALYSIS, "hybrid_detailed_analysis"),
    (RUN_ANNUAL_PLANT_ANALYSIS, "annual_plant_analysis"),
    (RUN_HEAT_RECOVERY_ANALYSIS, "heat_recovery_analysis"),
    (RUN_MIXED_SIZING_ANALYSIS, "mixed_sizing_analysis"),
    (RUN_SYSTEM_PERFORMANCE_MAP_ANALYSIS, "system_performance_map_analysis"),
    (RUN_FRASCOLD_PLOTS, "frascold_plots"),
    (RUN_GLYCOL_PLOTS, "glycol_plots"),
    (RUN_KIONA_PLOTS, "kiona_plots"),
    (RUN_VALIDATION_PLOTS, "validation_plots"),
    (RUN_PARAMETRIC_PLOTS, "parametric_plots"),
    (RUN_DISPATCH_PLOTS, "dispatch_plots"),
    (RUN_BUFFER_PLOTS, "buffer_plots"),
    (RUN_ACTUAL_STAGING_PLOTS, "actual_staging_plots"),
    (RUN_CARNOT_PLOTS, "carnot_plots"),
    (RUN_STANDARD_SEASONAL_PLOTS, "standard_seasonal_plots"),
    (RUN_ANNUAL_LOAD_PLOTS, "annual_load_plots"),
    (RUN_HYBRID_PLOTS, "hybrid_plots"),
    (RUN_HYBRID_DETAILED_PLOTS, "hybrid_detailed_plots"),
    (RUN_ANNUAL_PLANT_PLOTS, "annual_plant_plots"),
    (RUN_HEAT_RECOVERY_PLOTS, "heat_recovery_plots"),
    (RUN_MIXED_SIZING_PLOTS, "mixed_sizing_plots"),
    (RUN_OPTIMIZATION_SUMMARY_PLOTS, "optimization_summary_plots"),
    (RUN_SYSTEM_PERFORMANCE_MAP_PLOTS, "system_performance_map_plots"),
]

PLOT_KEYS = [key for _, key in TASKS if key.endswith("_plots")]


def run_script(key, number, total):
    path = SCRIPTS[key]
    if not path.exists():
        raise FileNotFoundError(path)

    print("\n" + "=" * 72)
    print(f"Running [{number:02d}/{total:02d}]: {path.name}")
    print("=" * 72)

    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - start

    if result.returncode != 0:
        print("Status: FAILED")
        print(f"Runtime: {elapsed:.1f} s")
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip())
        raise subprocess.CalledProcessError(result.returncode, result.args)

    print("Status: completed successfully")
    print(f"Runtime: {elapsed:.1f} s")


def main():
    if RUN_COMPLETE_PIPELINE_ONCE:
        keys = [key for _, key in TASKS]
    elif RUN_ALL_PLOTS_ONLY_ONCE:
        keys = PLOT_KEYS
    else:
        keys = [key for enabled, key in TASKS if enabled]

    for number, key in enumerate(keys, start=1):
        run_script(key, number, len(keys))

    print("\nSelected thesis-model tasks finished.")


if __name__ == "__main__":
    main()
