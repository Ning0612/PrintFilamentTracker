import argparse
import sys
from pathlib import Path

from .auth import AuthError
from .cloud_client import BambuCloudClient, EmptyResultError, NetworkError, RateLimitError
from .config import ConfigError, load_config
from .export_csv import export_csv
from .export_json import export_json
from .normalize import normalize_tasks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bambu-print-manager",
        description="從 Bambu Lab 雲端帳號匯出列印歷史",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="匯出列印歷史")
    export_parser.add_argument(
        "--format",
        choices=["json", "csv", "both"],
        default="json",
        help="輸出格式（預設：json）",
    )
    export_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="輸出目錄（預設：data/）",
    )
    return parser


def cmd_export(args: argparse.Namespace) -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        print(exc)
        return 1

    if args.output_dir is not None:
        config.output_dir = args.output_dir

    config.output_dir.mkdir(parents=True, exist_ok=True)

    client = BambuCloudClient(config)

    try:
        hits = client.fetch_all_tasks()
    except AuthError as exc:
        print(exc)
        return 1
    except RateLimitError as exc:
        print(exc)
        return 1
    except NetworkError as exc:
        print(exc)
        return 1
    except EmptyResultError as exc:
        print(exc)
        return 0

    try:
        client.save_raw_tasks(config.output_dir / "raw_tasks.json")
        records = normalize_tasks(hits)
        fmt = args.format
        if fmt in ("json", "both"):
            export_json(records, config.output_dir / "print_history.json")
        if fmt in ("csv", "both"):
            export_csv(records, config.output_dir / "print_history.csv")
    except OSError as exc:
        print(f"[ERROR] 檔案寫入失敗：{exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] 輸出時發生非預期錯誤：{exc}")
        return 1

    return 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "export":
            exit_code = cmd_export(args)
        else:
            parser.print_help()
            exit_code = 1
    except KeyboardInterrupt:
        print("\n[ABORT] 使用者中斷操作。")
        exit_code = 130

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
