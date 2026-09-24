"""
14_hybrid_operation.py

Classify measured heating-only, cooling-only and simultaneous/hybrid operation.
The discarded operating-state-hours output table/plot has been removed. The
classified 5-minute points, monthly hybrid overlap and compact hybrid summary
remain because they support the retained hybrid figures and heat-recovery work.
"""

from pathlib import Path
import importlib.util
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = PROJECT_ROOT / '00_CONFIG' / 'config.py'
TABLE_IO_FILE = PROJECT_ROOT / '00_CONFIG' / 'table_io.py'
INPUT_ANNUAL_DIAGNOSTICS = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'annual_load_diagnostics.csv'
OUTPUT_POINTS = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'hybrid_classified_points'
OUTPUT_MONTHLY = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'hybrid_monthly_summary'
OUTPUT_SUMMARY = PROJECT_ROOT / '06_RESULTS' / 'annual' / 'hybrid_summary'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

config = load('config_hybrid', CONFIG_FILE)
table_io = load('table_io_hybrid', TABLE_IO_FILE)


def main():
    data = table_io.read_table(INPUT_ANNUAL_DIAGNOSTICS)
    data['timestamp'] = pd.to_datetime(data['timestamp'], errors='coerce')

    start = pd.Timestamp(year=config.HYBRID_START_YEAR, month=config.HYBRID_START_MONTH, day=1)
    end = pd.Timestamp(year=config.HYBRID_END_YEAR, month=config.HYBRID_END_MONTH, day=1) + pd.offsets.MonthBegin(1)
    data = data[(data['timestamp'] >= start) & (data['timestamp'] < end)].copy()

    qh = pd.to_numeric(data['Heating_load_filtered_kW'], errors='coerce')
    qc = pd.to_numeric(data['Cooling_load_filtered_kW'], errors='coerce')
    valid = qh.notna() & qc.notna() & data['Ventilation_mode'].isin(['Heating', 'Cooling'])
    heat_active = qh >= config.HYBRID_ACTIVE_LOAD_THRESHOLD_KW
    cool_active = qc >= config.HYBRID_ACTIVE_LOAD_THRESHOLD_KW

    data['Operating_state'] = 'Not classifiable'
    data.loc[valid & ~heat_active & ~cool_active, 'Operating_state'] = 'Inactive / low load'
    data.loc[valid & heat_active & ~cool_active, 'Operating_state'] = 'Heating only'
    data.loc[valid & ~heat_active & cool_active, 'Operating_state'] = 'Cooling only'
    data.loc[valid & heat_active & cool_active, 'Operating_state'] = 'Hybrid'

    data['Recoverable_overlap_kW'] = np.nan
    hybrid_mask = data['Operating_state'].eq('Hybrid')
    data.loc[hybrid_mask, 'Recoverable_overlap_kW'] = np.minimum(qh.loc[hybrid_mask], qc.loc[hybrid_mask])

    classifiable = data[data['Operating_state'].ne('Not classifiable')].copy()
    hybrid = data[hybrid_mask].copy()
    dt_h = config.SOURCE_TIMESTEP_MINUTES / 60.0

    hybrid['month'] = hybrid['timestamp'].dt.to_period('M').astype(str)
    monthly = (
        hybrid.groupby('month')
        .agg(
            hybrid_hours=('timestamp', lambda s: len(s) * dt_h),
            hybrid_heating_MWh=('Heating_load_filtered_kW', lambda s: pd.to_numeric(s, errors='coerce').sum() * dt_h / 1000.0),
            hybrid_cooling_MWh=('Cooling_load_filtered_kW', lambda s: pd.to_numeric(s, errors='coerce').sum() * dt_h / 1000.0),
            recoverable_overlap_MWh=('Recoverable_overlap_kW', lambda s: pd.to_numeric(s, errors='coerce').sum() * dt_h / 1000.0),
        )
        .reset_index()
    )

    recoverable_MWh = hybrid['Recoverable_overlap_kW'].sum(min_count=1) * dt_h / 1000.0
    summary = pd.DataFrame([
        {'metric': 'Classifiable hours', 'value': len(classifiable) * dt_h, 'unit': 'h'},
        {'metric': 'Hybrid hours', 'value': len(hybrid) * dt_h, 'unit': 'h'},
        {'metric': 'Hybrid share of classifiable time', 'value': 100.0 * len(hybrid) / len(classifiable) if len(classifiable) else np.nan, 'unit': '%'},
        {'metric': 'Hybrid heating energy', 'value': hybrid['Heating_load_filtered_kW'].sum(min_count=1) * dt_h / 1000.0, 'unit': 'MWh_th'},
        {'metric': 'Hybrid cooling energy', 'value': hybrid['Cooling_load_filtered_kW'].sum(min_count=1) * dt_h / 1000.0, 'unit': 'MWh_th'},
        {'metric': 'First-order recoverable thermal overlap', 'value': recoverable_MWh, 'unit': 'MWh_th'},
        {'metric': 'Median recoverable thermal power during hybrid', 'value': hybrid['Recoverable_overlap_kW'].median(), 'unit': 'kW_th'},
        {'metric': 'Maximum recoverable thermal power during hybrid', 'value': hybrid['Recoverable_overlap_kW'].max(), 'unit': 'kW_th'},
    ])

    table_io.write_table(
        data, OUTPUT_POINTS, export_csv=True, export_xlsx=False,
        csv_separator=config.CSV_SEPARATOR, csv_decimal=config.CSV_DECIMAL,
        float_format=config.CSV_FLOAT_FORMAT, sheet_name='Points',
    )
    table_io.write_table(
        monthly, OUTPUT_MONTHLY, export_csv=config.EXPORT_CSV, export_xlsx=config.EXPORT_XLSX,
        csv_separator=config.CSV_SEPARATOR, csv_decimal=config.CSV_DECIMAL,
        float_format=config.CSV_FLOAT_FORMAT, sheet_name='Monthly',
    )
    table_io.write_table(
        summary, OUTPUT_SUMMARY, export_csv=config.EXPORT_CSV, export_xlsx=config.EXPORT_XLSX,
        csv_separator=config.CSV_SEPARATOR, csv_decimal=config.CSV_DECIMAL,
        float_format=config.CSV_FLOAT_FORMAT, sheet_name='Summary',
    )

    pass


if __name__ == '__main__':
    main()
