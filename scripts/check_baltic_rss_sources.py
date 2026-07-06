import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

import feedparser


ROOT = Path(__file__).resolve().parents[1]

CONFIG_PATH = ROOT / "config" / "baltic_sources.json"
STATUS_OUTPUT = ROOT / "data" / "baltic_rss_status.json"
DOCS_STATUS_OUTPUT = ROOT / "docs" / "data" / "baltic_rss_status.json"


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config file: {CONFIG_PATH}")

    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def check_source(source: Dict[str, Any]) -> Dict[str, Any]:
    name = source.get("name", "Unknown source")
    url = source.get("url", "")
    source_type = source.get("type", "unknown")
    source_group = source.get("source_group", "unknown")
    country = source.get("country")
    weight = source.get("weight", 1.0)

    checked_at = datetime.now(timezone.utc).isoformat()

    if not url:
        return {
            "name": name,
            "url": url,
            "type": source_type,
            "source_group": source_group,
            "country": country,
            "weight": weight,
            "status": "error",
            "entry_count": 0,
            "latest_title": None,
            "latest_published_at": None,
            "error": "Missing RSS URL",
            "checked_at": checked_at
        }

    try:
        parsed = feedparser.parse(url)

        entry_count = len(parsed.entries)

        latest_title = None
        latest_published_at = None

        if entry_count > 0:
            latest = parsed.entries[0]
            latest_title = getattr(latest, "title", None)
            latest_published_at = (
                getattr(latest, "published", None)
                or getattr(latest, "updated", None)
                or getattr(latest, "created", None)
            )

        bozo = bool(getattr(parsed, "bozo", False))
        bozo_exception = getattr(parsed, "bozo_exception", None)

        if entry_count > 0:
            status = "ok"
            error = None
        elif bozo:
            status = "warning"
            error = str(bozo_exception)
        else:
            status = "empty"
            error = None

        return {
            "name": name,
            "url": url,
            "type": source_type,
            "source_group": source_group,
            "country": country,
            "weight": weight,
            "status": status,
            "entry_count": entry_count,
            "latest_title": latest_title,
            "latest_published_at": latest_published_at,
            "error": error,
            "checked_at": checked_at
        }

    except Exception as exc:
        return {
            "name": name,
            "url": url,
            "type": source_type,
            "source_group": source_group,
            "country": country,
            "weight": weight,
            "status": "error",
            "entry_count": 0,
            "latest_title": None,
            "latest_published_at": None,
            "error": str(exc),
            "checked_at": checked_at
        }


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {
        "total_sources": len(results),
        "ok": 0,
        "warning": 0,
        "empty": 0,
        "error": 0,
        "total_entries": 0,
        "by_group": {}
    }

    for item in results:
        status = item.get("status", "error")
        group = item.get("source_group", "unknown")
        entry_count = int(item.get("entry_count", 0))

        summary[status] = summary.get(status, 0) + 1
        summary["total_entries"] += entry_count

        if group not in summary["by_group"]:
            summary["by_group"][group] = {
                "total_sources": 0,
                "ok": 0,
                "warning": 0,
                "empty": 0,
                "error": 0,
                "total_entries": 0
            }

        summary["by_group"][group]["total_sources"] += 1
        summary["by_group"][group][status] = (
            summary["by_group"][group].get(status, 0) + 1
        )
        summary["by_group"][group]["total_entries"] += entry_count

    return summary


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def main() -> None:
    config = load_config()
    sources = config.get("rss_sources", [])

    results = [check_source(source) for source in sources]

    payload = {
        "project": config.get("project", "baltic-hybrid-monitor"),
        "region": config.get("region", "Baltic states and Poland"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summarize(results),
        "sources": results
    }

    save_json(STATUS_OUTPUT, payload)
    save_json(DOCS_STATUS_OUTPUT, payload)

    print("Baltic RSS source health check completed.")
    print(f"Total sources: {payload['summary']['total_sources']}")
    print(f"OK: {payload['summary']['ok']}")
    print(f"Warnings: {payload['summary']['warning']}")
    print(f"Empty: {payload['summary']['empty']}")
    print(f"Errors: {payload['summary']['error']}")
    print(f"Total RSS entries detected: {payload['summary']['total_entries']}")
    print(f"Saved: {STATUS_OUTPUT}")
    print(f"Saved: {DOCS_STATUS_OUTPUT}")


if __name__ == "__main__":
    main()
