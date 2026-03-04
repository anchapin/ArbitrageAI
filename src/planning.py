"""
Research & Planning Module.

This module implements the "Research & Plan" step for the autonomy workflow.
"""

from datetime import datetime, timezone
from typing import Any

from traceloop.sdk.decorators import workflow

from src.llm_service import LLMService
from src.utils.logger import get_logger

from .context_extractor import ContextExtractor, WorkPlanGenerator
from .executor import PlanExecutor, PlanReviewer

logger = get_logger(__name__)


def _get_llm_for_task(domain: str | None) -> LLMService:
    """Get the appropriate LLMService based on task domain."""
    domain_lower = (domain or "").lower().strip()

    if domain_lower in {"legal", "accounting"}:
        logger.info(f"Using cloud model for {domain} task")
        return LLMService.for_complex_task()

    logger.info("Using local model for data analysis task")
    return LLMService.for_basic_admin()


class ResearchAndPlanOrchestrator:
    """Main orchestrator for the Research & Plan workflow."""

    def __init__(self, llm_service: LLMService | None = None, domain: str | None = None):
        """Initialize the orchestrator."""
        self.domain = domain
        if llm_service is None and domain:
            self.llm = _get_llm_for_task(domain)
        else:
            self.llm = llm_service or LLMService()

        self.context_extractor = ContextExtractor(self.llm)
        self.plan_generator = WorkPlanGenerator(self.llm)
        self.plan_executor = PlanExecutor(self.llm)
        self.plan_reviewer = PlanReviewer(self.llm)

    @workflow(name="research_and_plan_workflow")
    def execute_workflow(
        self,
        user_request: str,
        domain: str,
        csv_data: str | None = None,
        file_content: str | None = None,
        filename: str | None = None,
        file_type: str | None = None,
        api_key: str | None = None,
        sandbox_timeout: int = 120,
        task_type: str | None = None,
        output_format: str | None = None,
        max_review_attempts: int = 2,
    ) -> dict[str, Any]:
        """Execute the complete Research & Plan workflow."""
        workflow_result = {
            "workflow": "research_and_plan",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "steps": {},
        }

        # Step 1: Extract Context
        logger.info("Step 1: Extracting context from uploaded files...")
        extracted_context = self.context_extractor.extract_context(
            file_content=file_content,
            csv_data=csv_data,
            filename=filename,
            file_type=file_type,
            domain=domain,
        )
        workflow_result["steps"]["context_extraction"] = {
            "success": extracted_context.get("extraction_success", False),
            "context": extracted_context,
        }

        # Step 2: Generate Work Plan
        logger.info("Step 2: Creating work plan...")
        plan_result = self.plan_generator.create_work_plan(
            user_request=user_request,
            domain=domain,
            extracted_context=extracted_context,
            task_type=task_type,
            output_format=output_format,
        )

        if not plan_result.get("success"):
            workflow_result["failed_at"] = "plan_generation"
            workflow_result["error"] = plan_result.get("error", "Plan generation failed")
            return workflow_result

        work_plan = plan_result["plan"]
        workflow_result["steps"]["plan_generation"] = {"success": True, "plan": work_plan}

        exec_csv_data = extracted_context.get("raw_data") or csv_data or ""

        # Step 3: Execute Plan
        logger.info("Step 3: Executing work plan...")
        execution_result = self.plan_executor.execute_plan(
            work_plan=work_plan,
            csv_data=exec_csv_data,
            domain=domain,
            api_key=api_key,
            sandbox_timeout=sandbox_timeout,
        )

        workflow_result["steps"]["plan_execution"] = execution_result

        if not execution_result.get("success"):
            workflow_result["failed_at"] = "plan_execution"
            workflow_result["error"] = execution_result.get("error", "Execution failed")
            return workflow_result

        exec_result = execution_result.get("result", {})
        artifact_url = exec_result.get("image_url") or exec_result.get("file_url", "")

        if not artifact_url:
            workflow_result["failed_at"] = "artifact_generation"
            workflow_result["error"] = "No artifact was generated"
            return workflow_result

        # Step 4: Review Artifact
        logger.info("Step 4: Reviewing artifact against work plan...")
        review_attempts = 0
        approved = False
        current_feedback = ""

        while review_attempts < max_review_attempts and not approved:
            review_result = self.plan_reviewer.review_against_plan(
                artifact_url=artifact_url,
                work_plan=work_plan,
                user_request=user_request,
                domain=domain,
                execution_result=exec_result,
            )

            review_attempts += 1
            approved = review_result.get("approved", False)
            current_feedback = review_result.get("feedback", "")

            if not approved and review_attempts < max_review_attempts:
                logger.info(f"Review not approved, attempt {review_attempts + 1}/{max_review_attempts}")
                logger.info(f"Feedback: {current_feedback}")

                revision = self.plan_reviewer.regenerate_with_feedback(
                    work_plan=work_plan,
                    review_feedback=current_feedback,
                    csv_data=exec_csv_data,
                    domain=domain,
                )

                if revision.get("success"):
                    revised = revision.get("revision", {})
                    if revised.get("revised_approach"):
                        work_plan["approach"] = revised["revised_approach"]
                    if revised.get("new_steps"):
                        work_plan["steps"] = revised["new_steps"]

        workflow_result["steps"]["artifact_review"] = {
            "approved": approved,
            "feedback": current_feedback,
            "attempts": review_attempts,
            "review_result": review_result,
        }

        workflow_result["completed_at"] = datetime.now(timezone.utc).isoformat()
        workflow_result["success"] = approved

        if approved:
            workflow_result["artifact_url"] = artifact_url
            workflow_result["message"] = "Artifact approved by reviewer"
        else:
            workflow_result["message"] = f"Artifact not approved after {review_attempts} attempts: {current_feedback}"

        return workflow_result


def create_research_plan_workflow(
    user_request: str,
    domain: str,
    csv_data: str | None = None,
    file_content: str | None = None,
    filename: str | None = None,
    file_type: str | None = None,
    api_key: str | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Convenience function to execute the Research & Plan workflow."""
    orchestrator = ResearchAndPlanOrchestrator()
    return orchestrator.execute_workflow(
        user_request=user_request,
        domain=domain,
        csv_data=csv_data,
        file_content=file_content,
        filename=filename,
        file_type=file_type,
        api_key=api_key,
        **kwargs,
    )
