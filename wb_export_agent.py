import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from google_sheets_writer import GoogleSheetsExportStore
from models import ExportData, WildberriesApiError, WildberriesExportError
from wb_api import WildberriesExportClient


def main() -> int:
    _load_dotenv(Path(".env"))
    args = _parse_args()
    _configure_logging()
    start = time.monotonic()
    logger = logging.getLogger(__name__)
    logger.info(
        "wb_export_start",
        extra={
            "spreadsheet": args.spreadsheet,
            "report": args.report,
            "dry_run": args.dry_run,
        },
    )

    try:
        store = GoogleSheetsExportStore(args.spreadsheet)
        try:
            tokens = store.validate_and_read_tokens()
        finally:
            store.close()

        client = WildberriesExportClient(content_token=tokens.content, prices_token=tokens.prices)
        try:
            if args.report in {"all", "nomenclatures"}:
                nomenclatures = client.fetch_nomenclatures()
            else:
                nomenclatures = []
            if args.report in {"all", "prices"}:
                prices = client.fetch_price_template()
            else:
                prices = []
        finally:
            client.close()

        logger.info(
            "wb_export_counts",
            extra={"nomenclatures": len(nomenclatures), "prices": len(prices)},
        )
        if args.dry_run:
            print(
                "Dry-run успешно: "
                f"номенклатур={len(nomenclatures)}, строк шаблона цен={len(prices)}"
            )
            return 0

        store = GoogleSheetsExportStore(args.spreadsheet)
        try:
            backup_url = store.create_backup()
            spreadsheet_url = store.update_export_sheet(ExportData(nomenclatures, prices))
        finally:
            store.close()

        print(f"Выгрузка успешно записана: {spreadsheet_url}")
        print(f"Резервная копия: {backup_url}")
        return 0
    except WildberriesApiError as exc:
        logger.error(
            "wb_export_api_error",
            extra={"report": exc.report_name, "status_code": exc.status_code},
        )
        print(f"Ошибка API. {exc}", file=sys.stderr)
        return 1
    except WildberriesExportError as exc:
        logger.error("wb_export_error")
        print(f"Ошибка выгрузки: {exc}", file=sys.stderr)
        return 1
    finally:
        logger.info(
            "wb_export_finish",
            extra={"duration_seconds": round(time.monotonic() - start, 2)},
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Выгрузка данных Wildberries в Google Sheets")
    parser.add_argument(
        "--spreadsheet",
        "--url",
        required=True,
        help="Ссылка или id Google Sheets таблицы",
    )
    parser.add_argument(
        "--report",
        choices=["all", "nomenclatures", "prices"],
        default="all",
        help="Какой отчет выгружать",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Проверить ключи и API без записи в Google Sheets",
    )
    return parser.parse_args()


def _configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_SafeJsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


class _SafeJsonFormatter(logging.Formatter):
    _reserved = {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.fromtimestamp(record.created).isoformat(timespec="seconds"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in self._reserved or "token" in key.lower():
                continue
            payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


if __name__ == "__main__":
    raise SystemExit(main())
