"""
Add performance indexes for frequently queried fields

Issue #194: Add Database Indexes for Frequently Queried Fields

This migration adds indexes to improve query performance:
1. Task: client_id (client_email), status, created_at, marketplace_task_id
2. Bid: task_id (job_id), status, created_at, freelancer_id
3. ClientProfile: user_id (client_email), email
4. TaskExecution: task_id, status, started_at
5. Composite indexes: (client_id, status), (task_id, status)

Revision ID: 001_add_performance_indexes
Revises: 58948b63e4a7
Create Date: 2026-03-03

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_add_performance_indexes"
down_revision: str | None = "58948b63e4a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add performance indexes to frequently queried fields."""
    # =====================================================================
    # TASK TABLE INDEXES (Issue #194)
    # =====================================================================
    
    # Index on client_email for client-specific queries
    op.create_index(
        "idx_tasks_client_email",
        "tasks",
        ["client_email"],
        unique=False,
    )
    
    # Index on status for filtering by task status
    op.create_index(
        "idx_tasks_status",
        "tasks",
        ["status"],
        unique=False,
    )
    
    # Index on created_at for time-based queries
    op.create_index(
        "idx_tasks_created_at",
        "tasks",
        ["created_at"],
        unique=False,
    )
    
    # Index on stripe_session_id for payment lookups
    op.create_index(
        "idx_tasks_stripe_session_id",
        "tasks",
        ["stripe_session_id"],
        unique=False,
    )
    
    # Index on delivery_token for delivery lookups
    op.create_index(
        "idx_tasks_delivery_token",
        "tasks",
        ["delivery_token"],
        unique=False,
    )
    
    # Composite index: (client_email, status) for client task filtering
    op.create_index(
        "idx_tasks_client_status",
        "tasks",
        ["client_email", "status"],
        unique=False,
    )
    
    # Composite index: (status, created_at) for status-based time queries
    op.create_index(
        "idx_tasks_status_created",
        "tasks",
        ["status", "created_at"],
        unique=False,
    )
    
    # Index on is_high_value for profit protection queries
    op.create_index(
        "idx_tasks_is_high_value",
        "tasks",
        ["is_high_value"],
        unique=False,
        postgresql_where=sa.text("is_high_value = true"),
    )
    
    # =====================================================================
    # TASK_EXECUTIONS TABLE INDEXES (Issue #194)
    # =====================================================================
    
    # Index on task_id for task-execution lookups
    op.create_index(
        "idx_task_executions_task_id",
        "task_executions",
        ["task_id"],
        unique=False,
    )
    
    # Index on status for execution status filtering
    op.create_index(
        "idx_task_executions_status",
        "task_executions",
        ["status"],
        unique=False,
    )
    
    # Index on started_at for execution time queries
    op.create_index(
        "idx_task_executions_started_at",
        "task_executions",
        ["started_at"],
        unique=False,
    )
    
    # Index on completed_at for completion time queries
    op.create_index(
        "idx_task_executions_completed_at",
        "task_executions",
        ["completed_at"],
        unique=False,
    )
    
    # =====================================================================
    # TASK_PLANNING TABLE INDEXES
    # =====================================================================
    
    # Index on task_id for task-planning lookups
    op.create_index(
        "idx_task_planning_task_id",
        "task_planning",
        ["task_id"],
        unique=False,
    )
    
    # =====================================================================
    # TASK_REVIEWS TABLE INDEXES
    # =====================================================================
    
    # Index on task_id for task-review lookups
    op.create_index(
        "idx_task_reviews_task_id",
        "task_reviews",
        ["task_id"],
        unique=False,
    )
    
    # Index on status for review status filtering
    op.create_index(
        "idx_task_reviews_status",
        "task_reviews",
        ["status"],
        unique=False,
    )
    
    # =====================================================================
    # TASK_OUTPUTS TABLE INDEXES
    # =====================================================================
    
    # Index on task_id for task-output lookups
    op.create_index(
        "idx_task_outputs_task_id",
        "task_outputs",
        ["task_id"],
        unique=False,
    )
    
    # Index on output_type for output type filtering
    op.create_index(
        "idx_task_outputs_output_type",
        "task_outputs",
        ["output_type"],
        unique=False,
    )
    
    # =====================================================================
    # BIDS TABLE INDEXES (Issue #194)
    # =====================================================================
    
    # Index on job_id for job lookups
    op.create_index(
        "idx_bids_job_id",
        "bids",
        ["job_id"],
        unique=False,
    )
    
    # Index on status for bid status filtering
    op.create_index(
        "idx_bids_status",
        "bids",
        ["status"],
        unique=False,
    )
    
    # Index on created_at for time-based queries
    op.create_index(
        "idx_bids_created_at",
        "bids",
        ["created_at"],
        unique=False,
    )
    
    # Index on marketplace for marketplace-specific queries
    op.create_index(
        "idx_bids_marketplace",
        "bids",
        ["marketplace"],
        unique=False,
    )
    
    # Composite index: (marketplace, status) for marketplace status filtering
    op.create_index(
        "idx_bids_marketplace_status",
        "bids",
        ["marketplace", "status"],
        unique=False,
    )
    
    # Index on is_suitable for suitable bid filtering
    op.create_index(
        "idx_bids_is_suitable",
        "bids",
        ["is_suitable"],
        unique=False,
    )
    
    # =====================================================================
    # CLIENT_PROFILES TABLE INDEXES (Issue #194)
    # =====================================================================
    
    # Index on client_email for user lookups
    op.create_index(
        "idx_client_profiles_client_email",
        "client_profiles",
        ["client_email"],
        unique=False,
    )
    
    # Index on last_task_at for recent activity queries
    op.create_index(
        "idx_client_profiles_last_task_at",
        "client_profiles",
        ["last_task_at"],
        unique=False,
    )
    
    # =====================================================================
    # USER_QUOTAS TABLE INDEXES
    # =====================================================================
    
    # Index on user_id for user quota lookups
    op.create_index(
        "idx_user_quotas_user_id",
        "user_quotas",
        ["user_id"],
        unique=False,
    )
    
    # Composite index: (user_id, tier) for tier-based queries
    op.create_index(
        "idx_user_quotas_user_tier",
        "user_quotas",
        ["user_id", "tier"],
        unique=False,
    )
    
    # =====================================================================
    # QUOTA_USAGE TABLE INDEXES
    # =====================================================================
    
    # Index on user_id for user usage lookups
    op.create_index(
        "idx_quota_usage_user_id",
        "quota_usage",
        ["user_id"],
        unique=False,
    )
    
    # Index on billing_month for period-based queries
    op.create_index(
        "idx_quota_usage_billing_month",
        "quota_usage",
        ["billing_month"],
        unique=False,
    )
    
    # Composite index: (user_id, billing_month) for user period lookups
    op.create_index(
        "idx_quota_usage_user_month",
        "quota_usage",
        ["user_id", "billing_month"],
        unique=False,
    )
    
    # =====================================================================
    # RATE_LIMIT_LOGS TABLE INDEXES
    # =====================================================================
    
    # Index on user_id for user rate limit lookups
    op.create_index(
        "idx_rate_limit_logs_user_id",
        "rate_limit_logs",
        ["user_id"],
        unique=False,
    )
    
    # Index on timestamp for time-based queries
    op.create_index(
        "idx_rate_limit_logs_timestamp",
        "rate_limit_logs",
        ["timestamp"],
        unique=False,
    )
    
    # Composite index: (user_id, timestamp) for user time lookups
    op.create_index(
        "idx_rate_limit_logs_user_timestamp",
        "rate_limit_logs",
        ["user_id", "timestamp"],
        unique=False,
    )
    
    # =====================================================================
    # ARENA_COMPETITIONS TABLE INDEXES
    # =====================================================================
    
    # Index on task_id for task arena lookups
    op.create_index(
        "idx_arena_competitions_task_id",
        "arena_competitions",
        ["task_id"],
        unique=False,
    )
    
    # Index on status for competition status filtering
    op.create_index(
        "idx_arena_competitions_status",
        "arena_competitions",
        ["status"],
        unique=False,
    )
    
    # Index on created_at for time-based queries
    op.create_index(
        "idx_arena_competitions_created_at",
        "arena_competitions",
        ["created_at"],
        unique=False,
    )
    
    # Index on winner for winner-based queries
    op.create_index(
        "idx_arena_competitions_winner",
        "arena_competitions",
        ["winner"],
        unique=False,
    )
    
    # =====================================================================
    # SIMULATION_BIDS TABLE INDEXES
    # =====================================================================
    
    # Index on job_marketplace for marketplace lookups
    op.create_index(
        "idx_simulation_bids_marketplace",
        "simulation_bids",
        ["job_marketplace"],
        unique=False,
    )
    
    # Index on strategy_type for strategy analysis
    op.create_index(
        "idx_simulation_bids_strategy",
        "simulation_bids",
        ["strategy_type"],
        unique=False,
    )
    
    # Index on would_have_won for outcome analysis
    op.create_index(
        "idx_simulation_bids_outcome",
        "simulation_bids",
        ["would_have_won"],
        unique=False,
    )
    
    # =====================================================================
    # DISTRIBUTED_LOCKS TABLE INDEXES
    # =====================================================================
    
    # Index on lock_key for lock lookups
    op.create_index(
        "idx_distributed_locks_lock_key",
        "distributed_locks",
        ["lock_key"],
        unique=False,
    )
    
    # =====================================================================
    # SCHEDULED_TASKS TABLE INDEXES
    # =====================================================================
    
    # Index on status for scheduled task filtering
    op.create_index(
        "idx_scheduled_tasks_status",
        "scheduled_tasks",
        ["status"],
        unique=False,
    )
    
    # Index on next_run_at for scheduling queries
    op.create_index(
        "idx_scheduled_tasks_next_run_at",
        "scheduled_tasks",
        ["next_run_at"],
        unique=False,
    )
    
    # =====================================================================
    # SCHEDULE_HISTORY TABLE INDEXES
    # =====================================================================
    
    # Index on schedule_id for schedule history lookups
    op.create_index(
        "idx_schedule_history_schedule_id",
        "schedule_history",
        ["schedule_id"],
        unique=False,
    )
    
    # Index on execution_start for time-based queries
    op.create_index(
        "idx_schedule_history_execution_start",
        "schedule_history",
        ["execution_start"],
        unique=False,
    )


def downgrade() -> None:
    """Remove performance indexes."""
    # =====================================================================
    # TASK TABLE INDEXES
    # =====================================================================
    op.drop_index("idx_tasks_status_created", table_name="tasks")
    op.drop_index("idx_tasks_client_status", table_name="tasks")
    op.drop_index("idx_tasks_is_high_value", table_name="tasks")
    op.drop_index("idx_tasks_delivery_token", table_name="tasks")
    op.drop_index("idx_tasks_stripe_session_id", table_name="tasks")
    op.drop_index("idx_tasks_created_at", table_name="tasks")
    op.drop_index("idx_tasks_status", table_name="tasks")
    op.drop_index("idx_tasks_client_email", table_name="tasks")
    
    # =====================================================================
    # TASK_EXECUTIONS TABLE INDEXES
    # =====================================================================
    op.drop_index("idx_task_executions_completed_at", table_name="task_executions")
    op.drop_index("idx_task_executions_started_at", table_name="task_executions")
    op.drop_index("idx_task_executions_status", table_name="task_executions")
    op.drop_index("idx_task_executions_task_id", table_name="task_executions")
    
    # =====================================================================
    # TASK_PLANNING TABLE INDEXES
    # =====================================================================
    op.drop_index("idx_task_planning_task_id", table_name="task_planning")
    
    # =====================================================================
    # TASK_REVIEWS TABLE INDEXES
    # =====================================================================
    op.drop_index("idx_task_reviews_status", table_name="task_reviews")
    op.drop_index("idx_task_reviews_task_id", table_name="task_reviews")
    
    # =====================================================================
    # TASK_OUTPUTS TABLE INDEXES
    # =====================================================================
    op.drop_index("idx_task_outputs_output_type", table_name="task_outputs")
    op.drop_index("idx_task_outputs_task_id", table_name="task_outputs")
    
    # =====================================================================
    # BIDS TABLE INDEXES
    # =====================================================================
    op.drop_index("idx_bids_is_suitable", table_name="bids")
    op.drop_index("idx_bids_marketplace_status", table_name="bids")
    op.drop_index("idx_bids_marketplace", table_name="bids")
    op.drop_index("idx_bids_created_at", table_name="bids")
    op.drop_index("idx_bids_status", table_name="bids")
    op.drop_index("idx_bids_job_id", table_name="bids")
    
    # =====================================================================
    # CLIENT_PROFILES TABLE INDEXES
    # =====================================================================
    op.drop_index("idx_client_profiles_last_task_at", table_name="client_profiles")
    op.drop_index("idx_client_profiles_client_email", table_name="client_profiles")
    
    # =====================================================================
    # USER_QUOTAS TABLE INDEXES
    # =====================================================================
    op.drop_index("idx_user_quotas_user_tier", table_name="user_quotas")
    op.drop_index("idx_user_quotas_user_id", table_name="user_quotas")
    
    # =====================================================================
    # QUOTA_USAGE TABLE INDEXES
    # =====================================================================
    op.drop_index("idx_quota_usage_user_month", table_name="quota_usage")
    op.drop_index("idx_quota_usage_billing_month", table_name="quota_usage")
    op.drop_index("idx_quota_usage_user_id", table_name="quota_usage")
    
    # =====================================================================
    # RATE_LIMIT_LOGS TABLE INDEXES
    # =====================================================================
    op.drop_index("idx_rate_limit_logs_user_timestamp", table_name="rate_limit_logs")
    op.drop_index("idx_rate_limit_logs_timestamp", table_name="rate_limit_logs")
    op.drop_index("idx_rate_limit_logs_user_id", table_name="rate_limit_logs")
    
    # =====================================================================
    # ARENA_COMPETITIONS TABLE INDEXES
    # =====================================================================
    op.drop_index("idx_arena_competitions_winner", table_name="arena_competitions")
    op.drop_index("idx_arena_competitions_created_at", table_name="arena_competitions")
    op.drop_index("idx_arena_competitions_status", table_name="arena_competitions")
    op.drop_index("idx_arena_competitions_task_id", table_name="arena_competitions")
    
    # =====================================================================
    # SIMULATION_BIDS TABLE INDEXES
    # =====================================================================
    op.drop_index("idx_simulation_bids_outcome", table_name="simulation_bids")
    op.drop_index("idx_simulation_bids_strategy", table_name="simulation_bids")
    op.drop_index("idx_simulation_bids_marketplace", table_name="simulation_bids")
    
    # =====================================================================
    # DISTRIBUTED_LOCKS TABLE INDEXES
    # =====================================================================
    op.drop_index("idx_distributed_locks_lock_key", table_name="distributed_locks")
    
    # =====================================================================
    # SCHEDULED_TASKS TABLE INDEXES
    # =====================================================================
    op.drop_index("idx_scheduled_tasks_next_run_at", table_name="scheduled_tasks")
    op.drop_index("idx_scheduled_tasks_status", table_name="scheduled_tasks")
    
    # =====================================================================
    # SCHEDULE_HISTORY TABLE INDEXES
    # =====================================================================
    op.drop_index("idx_schedule_history_execution_start", table_name="schedule_history")
    op.drop_index("idx_schedule_history_schedule_id", table_name="schedule_history")
