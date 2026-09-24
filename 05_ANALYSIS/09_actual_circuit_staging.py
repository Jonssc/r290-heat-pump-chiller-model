"""
09_actual_circuit_staging.py

Final field-staging summary retained for the thesis.
Only the observed stable circuit-configuration counts and lead-circuit balance
are exported. The discarded capacity-request-by-circuit-count and individual
observed-two-circuit-period outputs have been removed.
"""

from pathlib import Path
import importlib.util
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = PROJECT_ROOT / '00_CONFIG' / 'config.py'
TABLE_IO_FILE = PROJECT_ROOT / '00_CONFIG' / 'table_io.py'
INPUT_STABLE_PERIODS = PROJECT_ROOT / '02_PROCESSED_DATA' / 'kiona_stable_periods.csv'
OUTPUT_CONFIGURATION_SUMMARY = PROJECT_ROOT / '06_RESULTS' / 'validation' / 'staging_configuration_summary'
OUTPUT_LEAD_CIRCUIT_BALANCE = PROJECT_ROOT / '06_RESULTS' / 'validation' / 'staging_lead_circuit_balance'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

config = load_module('config_actual_staging', CONFIG_FILE)
table_io = load_module('table_io_actual_staging', TABLE_IO_FILE)


def main():
    data = table_io.read_table(INPUT_STABLE_PERIODS)
    required = {
        'unit', 'mode', 'active_configuration',
        'mean_capacity_request_percent', 'nominal_sample_coverage_minutes',
    }
    missing = required - set(data.columns)
    if missing:
        raise KeyError(f'Stable-period file is missing: {sorted(missing)}')

    configuration = (
        data.groupby(['unit', 'mode', 'active_configuration'], dropna=False)
        .agg(
            stable_periods=('active_configuration', 'size'),
            total_nominal_hours=(
                'nominal_sample_coverage_minutes',
                lambda s: pd.to_numeric(s, errors='coerce').sum() / 60.0,
            ),
            mean_capacity_request_percent=('mean_capacity_request_percent', 'mean'),
            median_capacity_request_percent=('mean_capacity_request_percent', 'median'),
            min_capacity_request_percent=('mean_capacity_request_percent', 'min'),
            max_capacity_request_percent=('mean_capacity_request_percent', 'max'),
        )
        .reset_index()
    )

    balance_rows = []
    for (unit, mode), group in data.groupby(['unit', 'mode']):
        c1_only = group[group['active_configuration'].astype(str).eq('C1')]
        c2_only = group[group['active_configuration'].astype(str).eq('C2')]
        total_one = len(c1_only) + len(c2_only)
        balance_rows.append({
            'unit': unit,
            'mode': mode,
            'C1_only_periods': len(c1_only),
            'C2_only_periods': len(c2_only),
            'one_circuit_periods_total': total_one,
            'C1_share_of_one_circuit_periods_percent': 100.0 * len(c1_only) / total_one if total_one else np.nan,
            'C2_share_of_one_circuit_periods_percent': 100.0 * len(c2_only) / total_one if total_one else np.nan,
        })
    balance = pd.DataFrame(balance_rows)

    table_io.write_table(
        configuration, OUTPUT_CONFIGURATION_SUMMARY,
        export_csv=config.EXPORT_CSV, export_xlsx=config.EXPORT_XLSX,
        csv_separator=config.CSV_SEPARATOR, csv_decimal=config.CSV_DECIMAL,
        float_format=config.CSV_FLOAT_FORMAT, sheet_name='Configurations',
    )
    table_io.write_table(
        balance, OUTPUT_LEAD_CIRCUIT_BALANCE,
        export_csv=config.EXPORT_CSV, export_xlsx=config.EXPORT_XLSX,
        csv_separator=config.CSV_SEPARATOR, csv_decimal=config.CSV_DECIMAL,
        float_format=config.CSV_FLOAT_FORMAT, sheet_name='LeadBalance',
    )

    pass


if __name__ == '__main__':
    main()
