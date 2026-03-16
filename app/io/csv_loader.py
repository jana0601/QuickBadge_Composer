from __future__ import annotations

import csv
from pathlib import Path


REQUIRED_COLUMNS = ("person_name", "coupon_code")


def load_people_csv(csv_path: str | Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row.")
        missing = [col for col in REQUIRED_COLUMNS if col not in reader.fieldnames]
        if missing:
            raise ValueError(f"CSV missing required columns: {', '.join(missing)}")
        for index, row in enumerate(reader, start=2):
            person_name = (row.get("person_name") or "").strip()
            coupon_code = (row.get("coupon_code") or "").strip()
            if not person_name or not coupon_code:
                raise ValueError(
                    f"Row {index} is invalid: person_name and coupon_code are required."
                )
            rows.append({"person_name": person_name, "coupon_code": coupon_code})
    if not rows:
        raise ValueError("CSV has no data rows.")
    return rows

