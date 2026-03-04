"""
Planning Module - Client Preference Memory and Context Extraction.

This module handles client preference memory and context extraction
for the Research & Plan workflow.
"""

from datetime import datetime, timezone
from typing import Any

from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_client_preferences_from_tasks(
    client_email: str, db_session=None,
) -> dict[str, Any]:
    """
    Query the Task table for previous review_feedback from the same client_email.

    Extracts preferences from past review feedback to help the agent
    avoid failing ArtifactReviewer step.
    """
    preferences = {
        "has_history": False,
        "preferred_colors": [],
        "preferred_fonts": [],
        "preferred_chart_types": [],
        "preferred_output_formats": [],
        "style_preferences": {},
        "past_feedback": [],
        "total_previous_tasks": 0,
        "successful_tasks": 0,
        "failed_tasks": 0,
        "preferences_summary": "",
    }

    if not client_email:
        return preferences

    try:
        from src.api.database import SessionLocal
        from src.api.models import Task

        should_close_session = False
        if db_session is None:
            db_session = SessionLocal()
            should_close_session = True

        try:
            past_tasks = (
                db_session.query(Task)
                .filter(
                    Task.client_email == client_email,
                    Task.review_feedback.isnot(None),
                    Task.review_feedback,
                )
                .order_by(Task.created_at.desc())
                .limit(20)
                .all()
            )

            preferences["total_previous_tasks"] = len(past_tasks)

            if not past_tasks:
                return preferences

            preferences["has_history"] = True

            for task in past_tasks:
                feedback = task.review_feedback
                if feedback:
                    preferences["past_feedback"].append({
                        "task_id": task.id,
                        "domain": task.domain,
                        "feedback": feedback,
                        "approved": task.review_approved,
                        "created_at": task.created_at.isoformat() if task.created_at else None,
                    })

                    if task.review_approved:
                        preferences["successful_tasks"] += 1
                    else:
                        preferences["failed_tasks"] += 1

                    extracted = _extract_preferences_from_feedback(feedback)
                    _merge_preferences(preferences, extracted)

            preferences["preferences_summary"] = _generate_preferences_summary(preferences)

        finally:
            if should_close_session:
                db_session.close()

    except Exception as e:
        logger.error(f"Error getting client preferences: {e}")

    return preferences


def _extract_preferences_from_feedback(feedback: str) -> dict[str, Any]:
    """Extract specific preferences from review feedback text."""
    extracted = {
        "preferred_colors": [],
        "preferred_fonts": [],
        "preferred_chart_types": [],
        "preferred_output_formats": [],
        "style_preferences": {},
    }

    feedback_lower = feedback.lower()

    colors = ["blue", "red", "green", "yellow", "orange", "purple", "pink", "black", "white", "gray", "grey", "brown", "cyan", "magenta", "navy", "teal"]
    for color in colors:
        if color in feedback_lower:
            extracted["preferred_colors"].append(color)

    fonts = ["times new roman", "arial", "helvetica", "calibri", "verdana", "georgia", "courier", "consolas", "tahoma", "trebuchet", "impact"]
    for font in fonts:
        if font in feedback_lower:
            extracted["preferred_fonts"].append(font)

    chart_types = ["bar", "line", "pie", "scatter", "histogram", "area", "radar", "bubble"]
    for chart in chart_types:
        if chart in feedback_lower:
            extracted["preferred_chart_types"].append(chart)

    formats = ["image", "docx", "pdf", "xlsx", "excel", "spreadsheet", "document"]
    for fmt in formats:
        if fmt in feedback_lower:
            if fmt in {"excel", "spreadsheet"}:
                extracted["preferred_output_formats"].append("xlsx")
            elif fmt == "document":
                extracted["preferred_output_formats"].append("docx")
            else:
                extracted["preferred_output_formats"].append(fmt)

    style_keywords = {
        "formal": ["formal", "professional", "business"],
        "detailed": ["detailed", "comprehensive", "thorough"],
        "simple": ["simple", "minimal", "clean", "minimalist"],
        "colorful": ["colorful", "vibrant", "bright"],
        "dark": ["dark", "dark mode", "night"],
        "modern": ["modern", "contemporary", "sleek"],
        "classic": ["classic", "traditional"],
    }

    for style, keywords in style_keywords.items():
        for keyword in keywords:
            if keyword in feedback_lower:
                extracted["style_preferences"][style] = True
                break

    return extracted


def _merge_preferences(target: dict[str, Any], source: dict[str, Any]):
    """Merge extracted preferences into target, avoiding duplicates."""
    for key in ["preferred_colors", "preferred_fonts", "preferred_chart_types", "preferred_output_formats"]:
        if source.get(key):
            existing = set(target.get(key, []))
            existing.update(source[key])
            target[key] = list(existing)

    if source.get("style_preferences"):
        target["style_preferences"].update(source["style_preferences"])


def _generate_preferences_summary(preferences: dict[str, Any]) -> str:
    """Generate a human-readable summary of preferences for LLM prompts."""
    parts = []

    if preferences.get("preferred_colors"):
        parts.append(f"Colors: {', '.join(preferences['preferred_colors'])}")

    if preferences.get("preferred_fonts"):
        parts.append(f"Fonts: {', '.join(preferences['preferred_fonts'])}")

    if preferences.get("preferred_chart_types"):
        parts.append(f"Chart types: {', '.join(preferences['preferred_chart_types'])}")

    if preferences.get("preferred_output_formats"):
        parts.append(f"Output formats: {', '.join(preferences['preferred_output_formats'])}")

    style = preferences.get("style_preferences", {})
    if style:
        style_list = [k for k, v in style.items() if v]
        if style_list:
            parts.append(f"Style: {', '.join(style_list)}")

    if parts:
        return (
            "Client preferences from past tasks: "
            + " | ".join(parts)
            + f" ({preferences['successful_tasks']}/{preferences['total_previous_tasks']} tasks successful)"
        )

    return "No preferences recorded yet"


def save_client_preferences(
    client_email: str,
    task_id: str,
    review_feedback: str,
    review_approved: bool,
    domain: str,
    db_session=None,
):
    """Save or update client preferences based on task review feedback."""
    if not client_email:
        return

    try:
        from src.api.database import SessionLocal
        from src.api.models import ClientProfile

        should_close_session = False
        if db_session is None:
            db_session = SessionLocal()
            should_close_session = True

        try:
            profile = (
                db_session.query(ClientProfile)
                .filter(ClientProfile.client_email == client_email)
                .first()
            )

            if not profile:
                profile = ClientProfile(client_email=client_email)
                db_session.add(profile)

            profile.total_tasks = (profile.total_tasks or 0) + 1
            if review_approved:
                profile.completed_tasks = (profile.completed_tasks or 0) + 1
            else:
                profile.failed_tasks = (profile.failed_tasks or 0) + 1

            profile.last_task_at = datetime.now(timezone.utc)

            extracted = _extract_preferences_from_feedback(review_feedback)

            if extracted.get("preferred_colors"):
                existing_colors = set(profile.preferred_colors or [])
                existing_colors.update(extracted["preferred_colors"])
                profile.preferred_colors = list(existing_colors)

            if extracted.get("preferred_fonts"):
                existing_fonts = set(profile.preferred_fonts or [])
                existing_fonts.update(extracted["preferred_fonts"])
                profile.preferred_fonts = list(existing_fonts)

            if extracted.get("preferred_chart_types"):
                existing_charts = set(profile.preferred_chart_types or [])
                existing_charts.update(extracted["preferred_chart_types"])
                profile.preferred_chart_types = list(existing_charts)

            if extracted.get("preferred_output_formats"):
                existing_formats = set(profile.preferred_output_formats or [])
                existing_formats.update(extracted["preferred_output_formats"])
                profile.preferred_output_formats = list(existing_formats)

            if extracted.get("style_preferences"):
                current_style = profile.style_preferences or {}
                current_style.update(extracted["style_preferences"])
                profile.style_preferences = current_style

            history = profile.feedback_history or []
            history.append({
                "task_id": task_id,
                "domain": domain,
                "feedback": review_feedback,
                "approved": review_approved,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            profile.feedback_history = history[-20:]

            db_session.commit()
            logger.info(f"Updated client preferences for {client_email}")

        finally:
            if should_close_session:
                db_session.close()

    except Exception as e:
        logger.error(f"Error saving client preferences: {e}")
