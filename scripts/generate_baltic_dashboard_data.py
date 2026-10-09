
from pathlib import Path
import ast
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "generate_baltic_dashboard_data.py"

ELIGIBILITY_CHECK = """
        eligibility = event.get("index_eligibility") or {}
        if (
            isinstance(eligibility, dict)
            and eligibility.get("eligible", True) is False
        ):
            continue

"""

REVIEW_FUNCTION = '''
def build_manual_review_queue(scored):
    """Create an advisory queue without changing event classifications."""
    events = get_scored_events(scored)
    items = []

    for event in events:
        reasons = []

        lifecycle = event.get("lifecycle_review") or {}
        geography = event.get("geographic_review") or {}
        date_review = event.get("event_date_review") or {}

        if not isinstance(lifecycle, dict):
            lifecycle = {}
        if not isinstance(geography, dict):
            geography = {}
        if not isinstance(date_review, dict):
            date_review = {}

        if lifecycle.get("status") == "needs_review":
            reasons.append("lifecycle_uncertain")

        if geography.get("status") in (
            "mixed_geography_review",
            "outside_core_area_review"
        ):
            reasons.append("geographic_scope_uncertain")

        if date_review.get("status") == "explicit_date_needs_verification":
            reasons.append("event_date_verification")

        if not reasons:
            continue

        items.append({
            "event_id": event.get("event_id", event.get("id")),
            "title": event.get("title"),
            "url": event.get("url"),
            "published_at": event.get("published_at"),
            "event_subtype": event.get("event_subtype"),
            "hybrid_threat_score": event.get("hybrid_threat_score"),
            "reasons": reasons,
            "review_status": "pending",
            "index_eligible": (
                (event.get("index_eligibility") or {})
                .get("eligible", True)
            )
        })

    items.sort(
        key=lambda item: item.get("published_at") or "",
        reverse=True
    )

    return {
        "pending_count": len(items),
        "items": items,
        "note": (
            "Advisory review queue. Events remain unchanged "
            "until a separate manual decision is recorded."
        )
    }


'''


def patch_dashboard(source):
    original = source

    function_start = source.find("def calculate_v32_indices(")
    function_end = source.find(
        "\ndef calculate_country_v32_index(",
        function_start
    )

    if function_start < 0 or function_end < 0:
        raise RuntimeError(
            "Cannot locate the existing index calculation function."
        )

    function = source[function_start:function_end]

    if "eligibility.get(\"eligible\", True) is False" not in function:
        marker = "    for event in events:\n"

        if function.count(marker) != 1:
            raise RuntimeError(
                "Unexpected structure of index calculation."
            )

        function = function.replace(
            marker,
            marker + ELIGIBILITY_CHECK,
            1
        )

        source = (
            source[:function_start]
            + function
            + source[function_end:]
        )

    duplicate = '''        daily_indices = calculate_v32_indices(
            daily_events
        )

        rolling_indices = calculate_v32_indices('''

    replacement = '''        rolling_indices = calculate_v32_indices('''

    if duplicate in source:
        source = source.replace(
            duplicate,
            replacement,
            1
        )
    elif source == original:
        raise RuntimeError(
            "Cannot locate the historical calculation fix."
        )

    if "def build_manual_review_queue(" not in source:
        anchor = "def calculate_v32_indices("

        if anchor not in source:
            raise RuntimeError(
                "Cannot locate review queue insertion point."
            )

        source = source.replace(
            anchor,
            REVIEW_FUNCTION + anchor,
            1
        )

    if '"manual_review_queue": build_manual_review_queue(scored)' not in source:
        marker = '''        "data_quality":
            build_data_quality(
                scored
            ),'''

        if marker not in source:
            raise RuntimeError(
                "Cannot locate dashboard output data structure."
            )

        source = source.replace(
            marker,
            '''        "manual_review_queue":
            build_manual_review_queue(scored),

''' + marker,
            1
        )

    ast.parse(source, filename=str(TARGET))
    return source


def main():
    if not TARGET.exists():
        raise FileNotFoundError(TARGET)

    original = TARGET.read_text(encoding="utf-8")
    patched = patch_dashboard(original)

    if patched == original:
        print("Dashboard patch already applied.")
        return

    TARGET.write_text(patched, encoding="utf-8")

    print("Dashboard patch applied successfully.")
    print("Original dashboard functions preserved.")
    print("Lifecycle eligibility filter enabled.")
    print("Historical calculation corrected.")
    print("Manual review queue added.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Dashboard patch failed: {exc}", file=sys.stderr)
        sys.exit(1)
