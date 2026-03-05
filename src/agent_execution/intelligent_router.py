"""
Intelligent Task Routing System.

This module provides ML-based task classification and automatic routing
to optimize task distribution and improve success rates.
"""

from datetime import datetime
from typing import Any

from traceloop.sdk.decorators import workflow

from src.utils.logger import get_logger

from .classifiers import TaskClassifier
from .handlers import HandlerFactory
from .models import RouteDecision, TaskProfile
from .performance import PerformanceTracker

logger = get_logger(__name__)


class IntelligentRouter:
    """Intelligent task router using ML classification and performance data."""

    def __init__(self, db_session=None, model_path: str | None = None):
        """
        Initialize the intelligent router.

        Args:
            db_session: Database session for performance tracking
            model_path: Optional path to load pre-trained models
        """
        self.classifier = TaskClassifier(model_path)
        self.performance_tracker = PerformanceTracker(db_session)
        self.handler_factory = HandlerFactory()

        self.confidence_threshold = 0.7
        self.anomaly_threshold = 0.8
        self.performance_weight = 0.6
        self.ml_weight = 0.4

        self.handler_capabilities = {
            "legal_specialist": {
                "domains": ["legal"],
                "formats": ["docx", "pdf"],
                "complexity": ["high", "medium"],
            },
            "accounting_specialist": {
                "domains": ["accounting"],
                "formats": ["xlsx", "pdf"],
                "complexity": ["high", "medium"],
            },
            "visualization_specialist": {
                "domains": ["data_analysis"],
                "formats": ["image"],
                "complexity": ["medium", "low"],
            },
            "document_generator": {
                "domains": ["legal", "accounting", "data_analysis"],
                "formats": ["docx", "pdf"],
                "complexity": ["medium", "low"],
            },
            "spreadsheet_generator": {
                "domains": ["accounting", "data_analysis"],
                "formats": ["xlsx"],
                "complexity": ["medium", "low"],
            },
            "report_generator": {
                "domains": ["data_analysis"],
                "formats": ["docx", "pdf"],
                "complexity": ["medium", "low"],
            },
            "standard_handler": {
                "domains": ["data_analysis"],
                "formats": ["image"],
                "complexity": ["low"],
            },
        }

    @workflow(name="intelligent_routing")
    async def route_task(
        self,
        domain: str,
        user_request: str,
        csv_data: str,
        task_type: str | None = None,
        output_format: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Route a task using intelligent classification."""
        task_profile = self._create_task_profile(
            domain, user_request, csv_data, task_type, output_format,
        )

        try:
            classification = self.classifier.classify(task_profile)
        except Exception as e:
            logger.warning(f"Classification error: {e}, using fallback", exc_info=True)
            classification = self.classifier._rule_based_classification(task_profile)

        try:
            performance_recommendations = (
                self.performance_tracker.get_handler_recommendations(task_profile)
            )
        except Exception as e:
            logger.warning(f"Performance recommendations error: {e}", exc_info=True)
            performance_recommendations = []

        decision = self._make_routing_decision(
            task_profile, classification, performance_recommendations,
        )

        result = await self._execute_with_handler(task_profile, decision, **kwargs)

        self.performance_tracker.record_execution(
            task_profile, result.get("success", False),
        )

        return {
            "routing_decision": decision,
            "classification": classification,
            "performance_recommendations": performance_recommendations,
            "execution_result": result,
            "task_profile": self._profile_to_dict(task_profile),
        }

    def _create_task_profile(
        self,
        domain: str,
        user_request: str,
        csv_data: str,
        task_type: str | None,
        output_format: str | None,
    ) -> TaskProfile:
        """Create a task profile from task parameters."""
        from .executor import TaskRouter

        first_line = csv_data.strip().split("\n")[0]
        csv_headers = [h.strip() for h in first_line.split(",")]

        complexity = self._calculate_complexity_score(user_request, csv_headers, domain)
        estimated_time = self._estimate_execution_time(complexity, output_format)
        success_rate = self._calculate_success_rate(domain, task_type, output_format)

        task_router = TaskRouter()

        return TaskProfile(
            task_id=f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            domain=domain,
            user_request=user_request,
            csv_headers=csv_headers,
            task_type=task_type or task_router.detect_task_type(user_request),
            output_format=output_format
            or task_router.detect_output_format(domain, task_type or "visualization"),
            complexity_score=complexity,
            estimated_time=estimated_time,
            success_rate=success_rate,
            model_used="llama-3.2",
            retry_count=0,
            review_attempts=0,
            created_at=datetime.now(),
        )

    @staticmethod
    def _calculate_complexity_score(
        user_request: str, csv_headers: list[str], domain: str,
    ) -> float:
        """Calculate task complexity score."""
        score = 0.0

        request_length = len(user_request.split())
        if request_length > 20:
            score += 0.3
        elif request_length > 10:
            score += 0.2
        else:
            score += 0.1

        if domain.lower() in {"legal", "accounting"}:
            score += 0.4
        else:
            score += 0.2

        num_columns = len(csv_headers)
        if num_columns > 10:
            score += 0.3
        elif num_columns > 5:
            score += 0.2
        else:
            score += 0.1

        if any(word in user_request.lower() for word in ["analyze", "predict", "forecast", "optimize"]):
            score += 0.2

        return min(score, 1.0)

    @staticmethod
    def _estimate_execution_time(complexity: float, output_format: str) -> float:
        """Estimate execution time based on complexity and output format."""
        base_time = 60
        time_multiplier = 1 + (complexity * 2)

        format_multipliers = {"image": 1.0, "docx": 1.5, "xlsx": 1.5, "pdf": 1.2}
        format_multiplier = format_multipliers.get(output_format, 1.0)

        return base_time * time_multiplier * format_multiplier

    @staticmethod
    def _calculate_success_rate(
        domain: str, task_type: str, output_format: str,
    ) -> float:
        """Calculate expected success rate."""
        domain_rates = {"legal": 0.85, "accounting": 0.90, "data_analysis": 0.95}
        base_rate = domain_rates.get(domain.lower(), 0.90)

        if task_type == "document":
            base_rate -= 0.05
        elif task_type == "spreadsheet":
            base_rate -= 0.03

        if output_format in {"docx", "xlsx"}:
            base_rate -= 0.02

        return max(0.0, min(1.0, base_rate))

    def _make_routing_decision(
        self,
        task_profile: TaskProfile,
        classification: dict[str, Any],
        performance_recommendations: list[dict[str, Any]],
    ) -> RouteDecision:
        """Make routing decision based on classification and performance."""
        ml_prediction = classification.get("predicted_handler", "standard_handler")
        ml_confidence = classification.get("confidence", 0.5)

        anomaly_score = classification.get("anomaly_score", 0.0)
        is_anomaly = anomaly_score > self.anomaly_threshold

        candidates = {}

        if ml_confidence > self.confidence_threshold:
            candidates[ml_prediction] = ml_confidence * self.ml_weight

        for rec in performance_recommendations[:3]:
            handler = rec["handler"]
            score = rec["score"] * self.performance_weight
            candidates[handler] = candidates.get(handler, 0) + score

        if candidates:
            best_handler = max(candidates, key=candidates.get)
            best_score = candidates[best_handler]
        else:
            best_handler = "standard_handler"
            best_score = 0.5

        reasoning = self._generate_reasoning(
            task_profile, classification, performance_recommendations,
            best_handler, is_anomaly,
        )

        fallback_handlers = [
            rec["handler"]
            for rec in performance_recommendations[:3]
            if rec["handler"] != best_handler
        ]

        if ml_prediction != best_handler and ml_prediction not in fallback_handlers:
            fallback_handlers.append(ml_prediction)

        return RouteDecision(
            handler_type=best_handler,
            confidence=best_score,
            reasoning=reasoning,
            estimated_performance={
                "success_rate": self._get_estimated_success_rate(best_handler, task_profile),
                "execution_time": self._get_estimated_time(best_handler, task_profile),
                "complexity_match": self._get_complexity_match(best_handler, task_profile),
            },
            fallback_handlers=fallback_handlers[:3],
        )

    def _generate_reasoning(
        self,
        task_profile: TaskProfile,
        classification: dict[str, Any],
        performance_recommendations: list[dict[str, Any]],
        selected_handler: str,
        is_anomaly: bool,
    ) -> str:
        """Generate human-readable reasoning for routing decision."""
        reasoning_parts = []

        if classification.get("method") == "ml_classification":
            reasoning_parts.append(
                f"ML classification predicted '{classification['predicted_handler']}' "
                f"with {classification['confidence']:.2%} confidence",
            )
        else:
            reasoning_parts.append("Used rule-based classification")

        perf_rec = next((r for r in performance_recommendations if r["handler"] == selected_handler), None)
        if perf_rec:
            reasoning_parts.append(
                f"Performance data shows {selected_handler} has {perf_rec['success_rate']:.1%} "
                f"success rate and handles {perf_rec['task_volume']} tasks",
            )

        if is_anomaly:
            reasoning_parts.append("Task detected as anomaly, using conservative routing")

        capabilities = self.handler_capabilities.get(selected_handler, {})
        if capabilities:
            reasoning_parts.append(
                f"Handler capabilities: domains={capabilities['domains']}, "
                f"formats={capabilities['formats']}",
            )

        return " | ".join(reasoning_parts)

    def _get_estimated_success_rate(self, handler: str, task_profile: TaskProfile) -> float:
        """Get estimated success rate for a handler and task."""
        perf_data = self.performance_tracker.metrics["success_rate"].get(handler, 0.8)
        complexity_penalty = max(0, 1 - task_profile.complexity_score)
        return perf_data * 0.7 + complexity_penalty * 0.3

    def _get_estimated_time(self, handler: str, task_profile: TaskProfile) -> float:
        """Get estimated execution time for a handler and task."""
        base_time = self.performance_tracker.metrics["avg_execution_time"].get(handler, 120)
        complexity_multiplier = 1 + (task_profile.complexity_score * 2)
        return base_time * complexity_multiplier

    def _get_complexity_match(self, handler: str, task_profile: TaskProfile) -> float:
        """Get complexity match score for a handler and task."""
        thresholds = self.performance_tracker.get_complexity_thresholds()
        handler_thresholds = thresholds.get(handler, {})

        if not handler_thresholds:
            return 0.5

        avg_complexity = handler_thresholds.get("avg", 0.5)
        task_complexity = task_profile.complexity_score

        return 1 - abs(avg_complexity - task_complexity)

    async def _execute_with_handler(
        self, task_profile: TaskProfile, decision: RouteDecision, **kwargs,
    ) -> dict[str, Any]:
        """Execute task with the selected handler."""
        handler_type = decision.handler_type

        try:
            handler = self.handler_factory.get_handler(handler_type)
            result = await handler.execute(task_profile, **kwargs)

            task_profile.execution_time = result.get("execution_time", 0)
            task_profile.actual_success = result.get("success", False)
            task_profile.model_used = result.get("model_used", "unknown")

            return result

        except Exception as e:
            logger.error(f"Task execution failed for handler {handler_type}: {e}", exc_info=True)

            for fallback_handler in decision.fallback_handlers:
                try:
                    fallback_handler_instance = self.handler_factory.get_handler(fallback_handler)
                    result = await fallback_handler_instance.execute(task_profile, **kwargs)

                    task_profile.execution_time = result.get("execution_time", 0)
                    task_profile.actual_success = result.get("success", False)
                    task_profile.model_used = result.get("model_used", "unknown")

                    logger.info(f"Task execution succeeded with fallback handler: {fallback_handler}")
                    return result

                except Exception as fallback_error:
                    logger.error(f"Fallback execution failed for {fallback_handler}: {fallback_error}", exc_info=True)
                    continue

            return {
                "success": False,
                "message": f"All handlers failed. Last error: {e!s}",
                "handler_type": handler_type,
                "execution_time": 0,
                "model_used": "none",
            }

    @staticmethod
    def _profile_to_dict(profile: TaskProfile) -> dict[str, Any]:
        """Convert TaskProfile to dictionary."""
        from dataclasses import asdict
        return asdict(profile)

    def get_routing_analytics(self) -> dict[str, Any]:
        """Get analytics on routing decisions and performance."""
        import numpy as np

        sample_profile = TaskProfile(
            task_id="sample",
            domain="data_analysis",
            user_request="Analyze sales data",
            csv_headers=["date", "sales", "region"],
            task_type="visualization",
            output_format="image",
            complexity_score=0.5,
            estimated_time=120,
            success_rate=0.9,
            model_used="llama-3.2",
            retry_count=0,
            review_attempts=0,
            created_at=datetime.now(),
        )

        performance_recommendations = (
            self.performance_tracker.get_handler_recommendations(sample_profile)
        )

        return {
            "total_tasks_routed": sum(
                self.performance_tracker.metrics["task_volume"].values(),
            ),
            "average_success_rate": np.mean(
                list(self.performance_tracker.metrics["success_rate"].values()),
            ) if self.performance_tracker.metrics["success_rate"] else 0.0,
            "handler_performance": self.performance_tracker.metrics,
            "top_handlers": performance_recommendations[:5] if performance_recommendations else [],
        }


# Module-level singleton instance
_router_instance: IntelligentRouter | None = None


def get_intelligent_router() -> IntelligentRouter:
    """Get the singleton IntelligentRouter instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = IntelligentRouter()
    return _router_instance


async def route_task_intelligently(
    task_profile: TaskProfile,
    db_session=None,
    **kwargs,
) -> tuple[RouteDecision, dict[str, Any]]:
    """
    Convenience function to route a task intelligently.

    Args:
        task_profile: The task profile to route
        db_session: Optional database session
        **kwargs: Additional arguments for execution

    Returns:
        Tuple of (RouteDecision, execution_result)
    """
    router = get_intelligent_router()
    decision = await router.route_task(task_profile)
    result = await router._execute_with_handler(task_profile, decision, **kwargs)
    return decision, result
