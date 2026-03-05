"""Advanced Analytics Dashboard with Predictive Insights.

This module provides comprehensive analytics and predictive insights
for the ArbitrageAI platform.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from traceloop.sdk.decorators import task

from src.api.database import get_db
from src.utils.logger import get_logger

from .engines import (
    AnomalyDetection,
    KPIAnalytics,
    PerformanceAnalytics,
    PredictiveAnalytics,
)
from .models import (
    AnalyticsSummary,
    AnomalyAlert,
    DashboardWidget,
    KPIResponse,
    PerformanceMetric,
    PredictionResult,
    PredictiveInsight,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"], responses={404: {"description": "Not found"}})


class AnalyticsAPI:
    """Main analytics API class combining all analytics engines."""

    def __init__(self, db: Session):
        """Initialize the analytics API."""
        self.kpi_analytics = KPIAnalytics(db)
        self.predictive_analytics = PredictiveAnalytics(db)
        self.anomaly_detection = AnomalyDetection(db)
        self.performance_analytics = PerformanceAnalytics(db)

    @task(name="get_analytics_summary")
    def get_analytics_summary(self, time_range: str = "24h") -> AnalyticsSummary:
        """Get comprehensive analytics summary."""
        kpis = self.kpi_analytics.calculate_kpis(time_range)
        predictive_insights = self._generate_predictive_insights()
        anomalies = self._get_anomalies_summary()
        performance_metrics = self.performance_analytics.analyze_performance()
        recommendations = self._generate_recommendations(kpis, performance_metrics)

        return AnalyticsSummary(
            kpis=kpis,
            predictive_insights=predictive_insights,
            anomalies=anomalies,
            performance_metrics=performance_metrics,
            recommendations=recommendations,
            last_updated=datetime.now(),
        )

    def _generate_predictive_insights(self) -> list[PredictiveInsight]:
        """Generate predictive insights for key metrics."""
        insights = []

        revenue_prediction = self.predictive_analytics.generate_predictions("revenue", 24)
        insights.append(PredictiveInsight(
            metric="revenue",
            prediction=revenue_prediction.prediction,
            confidence=revenue_prediction.confidence,
            trend="up" if revenue_prediction.prediction > 0 else "down",
            time_horizon="24h",
            explanation="Based on historical revenue patterns and current trends",
        ))

        tasks_prediction = self.predictive_analytics.generate_predictions("tasks", 168)
        insights.append(PredictiveInsight(
            metric="tasks",
            prediction=tasks_prediction.prediction,
            confidence=tasks_prediction.confidence,
            trend="stable",
            time_horizon="7d",
            explanation="Based on historical task submission patterns",
        ))

        return insights

    def _get_anomalies_summary(self) -> list[AnomalyAlert]:
        """Get summary of recent anomalies."""
        anomalies = []
        revenue_anomalies = self.anomaly_detection.detect_anomalies("revenue", "24h")
        anomalies.extend(revenue_anomalies)
        task_anomalies = self.anomaly_detection.detect_anomalies("tasks", "24h")
        anomalies.extend(task_anomalies)
        return anomalies

    @staticmethod
    def _generate_recommendations(
        kpis: KPIResponse, performance_metrics: list[PerformanceMetric],
    ) -> list[str]:
        """Generate actionable recommendations based on analytics."""
        recommendations = []

        if kpis.revenue_growth_rate < 0:
            recommendations.append("Revenue is declining. Consider reviewing pricing strategy.")

        if kpis.success_rate < 90:
            recommendations.append("Task success rate is below target. Review execution processes.")

        for metric in performance_metrics:
            if metric.name == "avg_completion_time" and metric.value > metric.target:
                recommendations.append(
                    f"Task completion time ({metric.value:.1f}h) exceeds target ({metric.target}h).",
                )
            elif metric.name == "queue_length" and metric.value > metric.target:
                recommendations.append(f"Task queue length ({metric.value}) is high.")

        if not recommendations:
            recommendations.append("System performance is within acceptable ranges.")

        return recommendations


@router.get("/kpis", response_model=KPIResponse)
@task(name="get_kpis_endpoint")
async def get_kpis(
    time_range: str = Query("24h", description="Time range: 24h, 7d, 30d, all"),
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get key performance indicators."""
    try:
        kpi_analytics = KPIAnalytics(db)
        return kpi_analytics.calculate_kpis(time_range)
    except Exception as e:
        logger.error(f"Failed to calculate KPIs: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate KPIs") from e


@router.get("/predictions/{metric}", response_model=PredictionResult)
@task(name="get_predictions_endpoint")
async def get_predictions(
    metric: str,
    horizon_hours: int = Query(24, description="Prediction horizon in hours"),
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get predictions for a specific metric."""
    try:
        predictive_analytics = PredictiveAnalytics(db)
        return predictive_analytics.generate_predictions(metric, horizon_hours)
    except Exception as e:
        logger.error(f"Failed to generate predictions: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate predictions") from e


@router.get("/anomalies/{metric}", response_model=list[AnomalyAlert])
@task(name="get_anomalies_endpoint")
async def get_anomalies(
    metric: str,
    time_range: str = Query("24h", description="Time range for anomaly detection"),
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get anomalies for a specific metric."""
    try:
        anomaly_detection = AnomalyDetection(db)
        return anomaly_detection.detect_anomalies(metric, time_range)
    except Exception as e:
        logger.error(f"Failed to detect anomalies: {e}")
        raise HTTPException(status_code=500, detail="Failed to detect anomalies") from e


@router.get("/performance", response_model=list[PerformanceMetric])
@task(name="get_performance_endpoint")
async def get_performance(db: Session = Depends(get_db)):  # noqa: B008
    """Get performance metrics."""
    try:
        performance_analytics = PerformanceAnalytics(db)
        return performance_analytics.analyze_performance()
    except Exception as e:
        logger.error(f"Failed to analyze performance: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze performance") from e


@router.get("/summary", response_model=AnalyticsSummary)
@task(name="get_analytics_summary_endpoint")
async def get_analytics_summary(
    time_range: str = Query("24h", description="Time range for analysis"),
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get comprehensive analytics summary."""
    try:
        analytics_api = AnalyticsAPI(db)
        return analytics_api.get_analytics_summary(time_range)
    except Exception as e:
        logger.error(f"Failed to get analytics summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get analytics summary") from e


@router.get("/recommendations", response_model=list[str])
@task(name="get_recommendations_endpoint")
async def get_recommendations(db: Session = Depends(get_db)):  # noqa: B008
    """Get actionable recommendations based on analytics."""
    try:
        analytics_api = AnalyticsAPI(db)
        summary = analytics_api.get_analytics_summary()
        return summary.recommendations
    except Exception as e:
        logger.error(f"Failed to get recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to get recommendations") from e


@router.get("/widgets", response_model=list[DashboardWidget])
@task(name="get_dashboard_widgets_endpoint")
async def get_dashboard_widgets(db: Session = Depends(get_db)):  # noqa: B008
    """Get configured dashboard widgets."""
    return [
        DashboardWidget(
            id="kpi_overview",
            type="metric",
            title="Key Performance Indicators",
            data_source="kpis",
            configuration={"time_range": "24h"},
        ),
        DashboardWidget(
            id="revenue_trend",
            type="chart",
            title="Revenue Trend",
            data_source="revenue",
            configuration={"chart_type": "line", "time_range": "7d"},
        ),
        DashboardWidget(
            id="task_completion",
            type="chart",
            title="Task Completion Rate",
            data_source="success_rate",
            configuration={"chart_type": "bar", "time_range": "7d"},
        ),
        DashboardWidget(
            id="anomalies",
            type="table",
            title="Recent Anomalies",
            data_source="anomalies",
            configuration={"limit": 10},
        ),
    ]


def register_analytics_routes(app):
    """Register analytics routes with the FastAPI application."""
    app.include_router(router)
