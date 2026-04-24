import csv
import json
from pathlib import Path

CSV_FIELDNAMES = [
    "print_name",
    "printer_name",
    "printer_id",
    "started_at",
    "ended_at",
    "duration_seconds",
    "total_used_weight_g",
    "filaments_json",
]


def export_csv(records: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow(_flatten_record(record))
    print(f"[OK] CSV 已輸出：{output_path}（{len(records)} 筆）")


def _flatten_record(record: dict) -> dict:
    flat = dict(record)
    flat["filaments_json"] = json.dumps(
        record.get("filaments") or [], ensure_ascii=False
    )
    return flat
