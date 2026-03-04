"""
Analytics Models.

Pydantic models and dataclasses for analytics.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class KPIResponse(BaseModel):
    """Key Performance Indicators response model."""

    total_revenue: float
    total_tasks: int
    success_rate: float
    avg_completion_time: float
    active_users: int
    revenue_growth_rate: float
    tasks_per_hour: float


class PredictiveInsight(BaseModel):
    """Predictive insight model."""

    metric: str
    prediction: float
    confidence: float
    trend: str
    time_horizon: str
    explanation: str


class AnomalyAlert(BaseModel):
    """Anomaly detection alert model."""

    metric: str
    value: float
    expected_range: tuple[float, float]
    severity: str
    timestamp: datetime
    description: str


class PerformanceMetric(BaseModel):
    """Performance metric model."""

    name: str
    value: float
    unit: str
    trend: float
    target: float | None = None


class DashboardWidget(BaseModel):
    """Dashboard widget configuration."""

    id: str
    type: str
    title: str
    data_source: str
    configuration: dict[str, Any]


class AnalyticsSummary(BaseModel):
    """Comprehensive analytics summary."""

    kpis: KPIResponse
    predictive_insights: list[PredictiveInsight]
    anomalies: list[AnomalyAlert]
    performance_metrics: list[PerformanceMetric]
    recommendations: list[str]
    last_updated: datetime


@dataclass
class TimeSeriesData:
    """Time series data for analytics."""

    timestamps: list[datetime]
    values: list[float]
    labels: list[str]


@dataclass
class PredictionResult:
    """Prediction result with confidence intervals."""

    prediction: float
    lower_bound: float
    upper_bound: float
    confidence: float
    model_accuracy: float
