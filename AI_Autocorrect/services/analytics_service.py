from typing import Any, Dict, List

from utils.database import get_dashboard_summary


def build_admin_dashboard(db_path: str) -> Dict[str, Any]:
    summary = get_dashboard_summary(db_path)

    scores = [item.get("confidence_score", 0) for item in summary.get("recent_corrections", [])]
    average_recent_confidence = round(sum(scores) / len(scores), 2) if scores else 0

    return {
        **summary,
        "average_recent_confidence": average_recent_confidence,
        "top_performing_language": _top_language(summary.get("language_distribution", [])),
        "activity_labels": [item["label"] for item in summary.get("activity_trend", [])],
        "activity_values": [item["value"] for item in summary.get("activity_trend", [])],
        "activity_confidences": [item["confidence"] for item in summary.get("activity_trend", [])],
    }


def _top_language(language_distribution: List[Dict[str, Any]]) -> str:
    if not language_distribution:
        return "N/A"
    return language_distribution[0]["label"]