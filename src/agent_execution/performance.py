"""Performance Tracker Module.

Tracks and analyzes task execution performance for continuous improvement.
"""

from collections import defaultdict
from datetime import datetime
from typing import Any

import numpy as np

from src.utils.logger import get_logger

from .models import TaskProfile

logger = get_logger(__name__)


class PerformanceTracker:
    """Tracks and analyzes task execution performance for continuous improvement."""

    def __init__(self, db_session=None):
        """Initialize performance tracker.

        Args:
            db_session: Database session for storing performance data
        """
        self.db_session = db_session
        self.performance_data = defaultdict(list)
        self.handler_performance = defaultdict(lambda: defaultdict(list))

        self.metrics = {
            "success_rate": {},
            "avg_execution_time": {},
            "avg_complexity": {},
            "task_volume": {},
        }

    def record_execution(self, task_profile: TaskProfile, actual_success: bool):
        """Record task execution results for performance analysis.

        Args:
            task_profile: Task profile
            actual_success: Whether the task was actually successful
        """
        handler = task_profile.model_used

        self.performance_data[handler].append(
            {
                "task_id": task_profile.task_id,
                "success": actual_success,
                "execution_time": task_profile.execution_time,
                "complexity": task_profile.complexity_score,
                "retry_count": task_profile.retry_count,
                "review_attempts": task_profile.review_attempts,
                "timestamp": datetime.now(),
            },
        )

        self.handler_performance[handler]["successes"].append(actual_success)
        if task_profile.execution_time:
            self.handler_performance[handler]["execution_times"].append(
                task_profile.execution_time,
            )
        self.handler_performance[handler]["complexities"].append(
            task_profile.complexity_score,
        )

        self._update_metrics(handler)

    def _update_metrics(self, handler: str):
        """Update performance metrics for a handler."""
        data = self.handler_performance[handler]

        if data["successes"]:
            self.metrics["success_rate"][handler] = sum(data["successes"]) / len(
                data["successes"],
            )

        if data["execution_times"]:
            self.metrics["avg_execution_time"][handler] = np.mean(
                data["execution_times"],
            )

        if data["complexities"]:
            self.metrics["avg_complexity"][handler] = np.mean(data["complexities"])

        self.metrics["task_volume"][handler] = len(data["successes"])

    def get_handler_recommendations(
        self, task_profile: TaskProfile,
    ) -> list[dict[str, Any]]:
        """Get handler recommendations based on performance data.

        Args:
            task_profile: Task profile to get recommendations for

        Returns:
            List of handler recommendations with scores
        """
        recommendations = []

        all_handlers = set(self.metrics["success_rate"].keys()) | set(
            self.metrics["avg_execution_time"].keys(),
        )

        for handler in all_handlers:
            success_rate = self.metrics["success_rate"].get(handler, 0.0)
            avg_time = self.metrics["avg_execution_time"].get(handler, 0.0)
            avg_complexity = self.metrics["avg_complexity"].get(handler, 0.0)
            volume = self.metrics["task_volume"].get(handler, 0)

            time_score = max(0, 1 - (avg_time / 600))
            complexity_score = min(1, avg_complexity / 1.0)
            volume_score = min(1, volume / 100)

            composite_score = (
                success_rate * 0.4
                + time_score * 0.2
                + complexity_score * 0.2
                + volume_score * 0.2
            )

            recommendations.append(
                {
                    "handler": handler,
                    "score": composite_score,
                    "success_rate": success_rate,
                    "avg_execution_time": avg_time,
                    "avg_complexity": avg_complexity,
                    "task_volume": volume,
                },
            )

        recommendations.sort(key=lambda x: x["score"], reverse=True)
        return recommendations

    def get_complexity_thresholds(self) -> dict[str, float]:
        """Calculate complexity thresholds for different handler types.

        Returns:
            Dictionary mapping handler types to complexity thresholds
        """
        thresholds = {}

        for handler, data in self.handler_performance.items():
            if data["complexities"]:
                complexities = data["complexities"]
                thresholds[handler] = {
                    "low": np.percentile(complexities, 25),
                    "medium": np.percentile(complexities, 50),
                    "high": np.percentile(complexities, 75),
                    "avg": np.mean(complexities),
                }

        return thresholds
