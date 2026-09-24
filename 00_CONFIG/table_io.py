"""
Common table input/output helpers.

"""

# ============================================================
# 1. IMPORTS
# ============================================================

from pathlib import Path
from typing import Optional
import pandas as pd


# ============================================================
# 2. AUTO-READ TABLE
# ============================================================

def resolve_table_path(path: Path) -> Path:
    """
    Resolve a generated table path robustly.

    CSV is the canonical generated-table format in the current project. If a
    script still supplies an older .xlsx path, the matching .csv file is used
    automatically when present. Raw-input workbooks still work normally.
    """
    path = Path(path)

    # Prefer the exact CSV stem whenever it exists.
    csv_candidate = path.with_suffix(".csv")
    if csv_candidate.exists():
        return csv_candidate

    if path.exists():
        return path

    # Backward compatibility for projects that still contain XLSX results.
    for suffix in (".xlsx", ".xlsm", ".xls"):
        candidate = path.with_suffix(suffix)
        if candidate.exists():
            return candidate

    raise FileNotFoundError(path)


def table_exists(path: Path) -> bool:
    try:
        resolve_table_path(path)
        return True
    except FileNotFoundError:
        return False


def read_table(path: Path, sheet_name: Optional[str] = None) -> pd.DataFrame:
    path = resolve_table_path(path)

    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet_name or 0)

    # Detect the delimiter so semicolon/decimal-comma files and ordinary
    # comma/decimal-point CSV files are both read correctly.
    lines = path.read_text(
        encoding="utf-8-sig",
        errors="replace",
    ).splitlines()

    if not lines:
        return pd.DataFrame()

    first_line = lines[0]

    if first_line.count(";") > first_line.count(","):
        return pd.read_csv(path, sep=";", decimal=",")

    return pd.read_csv(path, sep=",", decimal=".")


# ============================================================
# 3. EXPORT TABLE
# ============================================================

def write_table(
    dataframe: pd.DataFrame,
    base_path: Path,
    *,
    export_csv: bool = True,
    export_xlsx: bool = True,
    csv_separator: str = ";",
    csv_decimal: str = ",",
    float_format: str = "%.6f",
    sheet_name: str = "Data",
) -> dict:
    """Write a table to CSV and/or XLSX.

    base_path is supplied without a suffix, e.g. results / "validation_rows".
    """
    base_path = Path(base_path)
    base_path.parent.mkdir(parents=True, exist_ok=True)
    outputs = {}

    if export_csv:
        csv_path = base_path.with_suffix(".csv")
        dataframe.to_csv(
            csv_path,
            index=False,
            sep=csv_separator,
            decimal=csv_decimal,
            float_format=float_format,
        )
        outputs["csv"] = csv_path

    if export_xlsx:
        xlsx_path = base_path.with_suffix(".xlsx")
        # True XLSX output: every dataframe column is a separate Excel column.
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            dataframe.to_excel(writer, sheet_name=sheet_name[:31], index=False)
            ws = writer.book[sheet_name[:31]]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for column_cells in ws.columns:
                max_length = max(
                    len(str(cell.value)) if cell.value is not None else 0
                    for cell in column_cells
                )
                ws.column_dimensions[column_cells[0].column_letter].width = min(max(max_length + 2, 10), 34)
        outputs["xlsx"] = xlsx_path

    return outputs
