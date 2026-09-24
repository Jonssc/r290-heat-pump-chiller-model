"""
19_generate_system_performance_maps.py

Prepares only the retained component-optimization contour data:
- air-side effective UA x fan-speed multiplier;
- water-side effective UA x water-flow fraction.

The discarded setpoint, staging/frequency, active-unit/circuit and hybrid
cooling-share maps and their supporting calculations/tables have been removed.
"""

from pathlib import Path
import importlib.util
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = PROJECT_ROOT / '00_CONFIG' / 'config.py'
TABLE_IO_FILE = PROJECT_ROOT / '00_CONFIG' / 'table_io.py'

PARAMETRIC_FOLDER = PROJECT_ROOT / '06_RESULTS' / 'optimization' / 'parametric'
INPUT_REFERENCE = PARAMETRIC_FOLDER / '00_parametric_reference_points.csv'
INPUT_AIR_HEATING = PARAMETRIC_FOLDER / '11_heating_air_UA_x_fan_fixed_load.csv'
INPUT_AIR_COOLING = PARAMETRIC_FOLDER / '11_cooling_air_UA_x_fan_fixed_load.csv'
INPUT_WATER_HEATING = PARAMETRIC_FOLDER / '12_heating_water_UA_x_flow_fixed_load.csv'
INPUT_WATER_COOLING = PARAMETRIC_FOLDER / '12_cooling_water_UA_x_flow_fixed_load.csv'
OUTPUT_FOLDER = PARAMETRIC_FOLDER


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

config = load_module('config_component_maps', CONFIG_FILE)
table_io = load_module('table_io_component_maps', TABLE_IO_FILE)


def read_required(path):
    return table_io.read_table(path)


def export_table(dataframe, stem, sheet):
    table_io.write_table(
        dataframe, OUTPUT_FOLDER / stem,
        export_csv=config.EXPORT_CSV, export_xlsx=config.EXPORT_XLSX,
        csv_separator=config.CSV_SEPARATOR, csv_decimal=config.CSV_DECIMAL,
        float_format=config.CSV_FLOAT_FORMAT, sheet_name=sheet,
    )


def reference_row(reference, mode):
    q = reference[reference['mode'].astype(str).str.lower().eq(mode)]
    if q.empty:
        raise RuntimeError(f'No parametric reference row for {mode}.')
    return q.iloc[0]


def create_airside_table(mode, source_path, reference):
    data = read_required(source_path).copy()
    ref = reference_row(reference, mode)
    reference_target = float(ref['reference_target_Q_kW'])
    reference_efficiency = float(ref['reference_COP_or_EER'])
    reference_power = reference_target / reference_efficiency

    case_power = pd.to_numeric(data['Pcircuit_comp_plus_fan_kW'], errors='coerce')
    feasible = data['feasible'].astype(str).str.lower().isin(['true', '1']) & data['model_status'].astype(str).eq('OK')
    data['reference_power_kW'] = reference_power
    data['electrical_saving_vs_reference_percent'] = np.where(
        feasible & case_power.gt(0),
        100.0 * (reference_power - case_power) / reference_power,
        np.nan,
    )
    data['electrical_boundary'] = 'compressor + normal outdoor-coil fan; external hydronic pumps excluded'
    return data


def nearest_reference_case(data):
    score = (
        (pd.to_numeric(data['water_UA_multiplier'], errors='coerce') - 1.0).abs()
        + (pd.to_numeric(data['water_flow_fraction'], errors='coerce') - 1.0).abs()
    )
    return data.loc[score.idxmin()]


def create_waterside_table(mode, source_path):
    data = read_required(source_path).copy()
    reference = nearest_reference_case(data)
    reference_total_power = float(reference['Pcircuit_comp_plus_fan_kW']) + float(reference['screening_unit_pump_power_kW'])
    total_power = (
        pd.to_numeric(data['Pcircuit_comp_plus_fan_kW'], errors='coerce')
        + pd.to_numeric(data['screening_unit_pump_power_kW'], errors='coerce')
    )
    feasible = data['feasible'].astype(str).str.lower().isin(['true', '1']) & data['model_status'].astype(str).eq('OK')
    data['reference_total_power_with_unit_pump_kW'] = reference_total_power
    data['total_power_with_unit_pump_kW'] = total_power
    data['electrical_saving_vs_reference_percent'] = np.where(
        feasible & total_power.gt(0),
        100.0 * (reference_total_power - total_power) / reference_total_power,
        np.nan,
    )
    data['electrical_boundary'] = 'compressor + normal outdoor-coil fan + nameplate-based local Chiller Unit pump screening'
    return data


def main():
    reference = read_required(INPUT_REFERENCE)

    air_heating = create_airside_table('heating', INPUT_AIR_HEATING, reference)
    air_cooling = create_airside_table('cooling', INPUT_AIR_COOLING, reference)
    water_heating = create_waterside_table('heating', INPUT_WATER_HEATING)
    water_cooling = create_waterside_table('cooling', INPUT_WATER_COOLING)

    export_table(air_heating, '14_heating_air_UA_fan_map', 'HeatingAir')
    export_table(air_cooling, '15_cooling_air_UA_fan_map', 'CoolingAir')
    export_table(water_heating, '16_heating_water_UA_flow_map', 'HeatingWater')
    export_table(water_cooling, '17_cooling_water_UA_flow_map', 'CoolingWater')

    pass


if __name__ == '__main__':
    main()
