"""CSV parsing + scaled-value conversion for the importer.

All money/quantity parsing uses ``decimal.Decimal`` on the raw CSV strings —
NFR-10 forbids floats in money/quantity arithmetic paths.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB (Q-4)
MAX_ROWS = 5_000  # data rows excluding the header row (Q-4)

# Structural: header cells only uppercase letters, digits, spaces, and common
# separators. Headed CSVs from brokers are simple; anything exotic is a schema
# error the user must fix instead of silently mis-mapping.
_ALLOWED_HEADER_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-.+/()&"
)


class ImportError(Exception):
    """Unrecoverable import failure at file level (limits, schema, mappings)."""


@dataclass(frozen=True)
class CsvFile:
    header: list[str]
    rows: list[dict[str, str]]


def parse_csv(
    text: str, *, max_file_bytes: int = MAX_FILE_BYTES, max_rows: int = MAX_ROWS
) -> CsvFile:
    if len(text.encode("utf-8")) > max_file_bytes:
        raise ImportError(
            f"file exceeds the 5 MB import limit ({max_file_bytes // (1024 * 1024)} MB); "
            "split the file and try again"
        )
    if not text or not text.strip():
        raise ImportError("CSV input is empty; nothing to import")

    reader = csv.reader(io.StringIO(text))
    try:
        raw_rows = list(reader)
    except csv.Error as exc:  # structurally broken CSV
        raise ImportError(f"CSV could not be parsed: {exc}") from exc

    if not raw_rows:
        raise ImportError("CSV input is empty; nothing to import")

    header_cells = [cell.strip() for cell in raw_rows[0]]
    for cell in header_cells:
        if not cell or not all(char in _ALLOWED_HEADER_CHARS for char in cell):
            raise ImportError(f"unsupported header column name: {cell!r}")
    header = [cell.casefold() for cell in header_cells]
    if len(set(header)) != len(header):
        raise ImportError("CSV header contains duplicate column names")

    data_rows = raw_rows[1:]
    if len(data_rows) > max_rows:
        raise ImportError(
            f"import is limited to 5,000 rows per file (got {len(data_rows)} rows); "
            "split the file and try again"
        )

    rows: list[dict[str, str]] = []
    for line_no, cells in enumerate(data_rows, start=1):
        if len(cells) == 1 and not cells[0].strip():
            continue  # skip blank lines
        if len(cells) != len(header):
            raise ImportError(
                f"row {line_no} has {len(cells)} values but the header has {len(header)} columns"
            )
        for cell in cells:
            # Quote characters must appear only as field delimiters in the raw
            # text; a quote inside a parsed value means a broken/unquoted field.
            if '"' in cell:
                raise ImportError(
                    f"row {line_no} contains an unquoted quote character in a data field"
                )
        rows.append({field: value.strip() for field, value in zip(header, cells, strict=True)})

    if not rows:
        raise ImportError("CSV has no data rows")
    return CsvFile(header=header_cells, rows=rows)


_Q4 = Decimal("0.0001")
_CENTS = Decimal("0.01")


def _parse_decimal(value: str, *, scale: Decimal, label: str, max_decimals: int) -> int:
    text = str(value).strip()
    if not text:
        raise ImportError(f"{label} is required")
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ImportError(f"{label} is not a valid number: {text!r}") from exc
    if number < 0:
        raise ImportError(f"{label} must be non-negative")
    if number != number.quantize(scale):
        raise ImportError(f"{label} is limited to {max_decimals} decimals: {text!r}")
    return int(number * (Decimal("1").scaleb(max_decimals)))


def decimal_to_q4(value: str, *, label: str = "quantity") -> int:
    """Convert a decimal string to a quantity_q4 integer (×10⁴)."""
    return _parse_decimal(value, scale=_Q4, label=label, max_decimals=4)


def decimal_to_cents(value: str, *, label: str = "amount") -> int:
    """Convert a decimal string to an integer-cents amount."""
    return _parse_decimal(value, scale=_CENTS, label=label, max_decimals=2)


def decimal_to_volume(value: str, *, label: str = "volume") -> int:
    """Convert an integer share-volume string (no fractional shares)."""
    return _parse_decimal(value, scale=Decimal("1"), label=label, max_decimals=0)
