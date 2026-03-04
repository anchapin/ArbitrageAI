"""
Plan Executor and Reviewer.

This module handles plan execution and artifact review.
"""

from datetime import datetime, timezone
import json
from typing import Any

from src.llm_service import LLMService
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PlanExecutor:
    """Executes the work plan in the sandbox."""

    def __init__(self, llm_service: LLMService | None = None):
        """Initialize the plan executor."""
        self.llm = llm_service or LLMService()

    def execute_plan(
        self,
        work_plan: dict[str, Any],
        csv_data: str,
        domain: str,
        api_key: str | None = None,
        sandbox_timeout: int = 120,
    ) -> dict[str, Any]:
        """Execute the work plan to generate the artifact."""
        from src.agent_execution.executor import TaskRouter, execute_data_visualization

        user_request = work_plan.get("user_request", "")
        task_type = PlanExecutor._infer_task_type(work_plan)
        output_format = work_plan.get("output_format") or PlanExecutor._infer_output_format(work_plan)

        execution_log = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "steps_executed": [],
            "plan_title": work_plan.get("title", ""),
        }

        try:
            if output_format in {"docx", "pdf"}:
                router = TaskRouter(llm_service=self.llm)
                result = router.route(
                    domain=domain,
                    user_request=user_request,
                    csv_data=csv_data,
                    task_type=task_type,
                    output_format=output_format,
                    api_key=api_key,
                    sandbox_timeout=sandbox_timeout,
                )
            elif output_format == "xlsx":
                router = TaskRouter(llm_service=self.llm)
                result = router.route(
                    domain=domain,
                    user_request=user_request,
                    csv_data=csv_data,
                    task_type="spreadsheet",
                    output_format=output_format,
                    api_key=api_key,
                    sandbox_timeout=sandbox_timeout,
                )
            else:
                result = execute_data_visualization(
                    csv_data=csv_data,
                    user_request=user_request,
                    domain=domain,
                    api_key=api_key,
                    sandbox_timeout=sandbox_timeout,
                    llm_service=self.llm,
                    enable_pre_submission_review=True,
                )

            execution_log["completed_at"] = datetime.now(timezone.utc).isoformat()
            execution_log["steps_executed"] = work_plan.get("steps", [])
            execution_log["execution_result"] = result

            return {
                "success": result.get("success", False),
                "result": result,
                "execution_log": execution_log,
            }

        except Exception as e:
            execution_log["error"] = str(e)
            execution_log["completed_at"] = datetime.now(timezone.utc).isoformat()
            return {"success": False, "error": str(e), "execution_log": execution_log}

    @staticmethod
    def _infer_task_type(plan: dict[str, Any]) -> str:
        """Infer task type from work plan."""
        recommended = plan.get("recommended_chart_type", "")
        if recommended in {"bar", "line", "pie", "scatter", "histogram"}:
            return "visualization"
        if recommended == "table":
            return "spreadsheet"
        if recommended == "document":
            return "document"
        return "auto"

    @staticmethod
    def _infer_output_format(plan: dict[str, Any]) -> str:
        """Infer output format from work plan."""
        output_format = plan.get("output_format", "")
        if output_format in {"image", "docx", "xlsx", "pdf"}:
            return output_format
        return "image"


class PlanReviewer:
    """Reviews the generated artifact against the work plan."""

    def __init__(self, llm_service: LLMService | None = None):
        """Initialize the plan reviewer."""
        self.llm = llm_service or LLMService()

    def review_against_plan(
        self,
        artifact_url: str,
        work_plan: dict[str, Any],
        user_request: str,
        domain: str,
        execution_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Review the generated artifact against the work plan."""
        plan_title = work_plan.get("title", "")
        plan_steps = work_plan.get("steps", [])
        success_criteria = work_plan.get("success_criteria", [])
        potential_issues = work_plan.get("potential_issues", [])

        system_prompt = f"""You are an expert artifact reviewer for {domain} tasks.
Your job is to validate that the generated artifact meets the work plan requirements.

Respond with a JSON object containing:
{{
    "approved": true/false,
    "feedback": "Detailed feedback if not approved",
    "issues": ["List of specific issues found"],
    "criteria_met": ["Success criteria that were met"],
    "criteria_not_met": ["Success criteria that were not met"],
    "plan_adherence": "high|medium|low"
}}"""

        prompt = f"""Work Plan Title: {plan_title}
Work Plan Approach: {work_plan.get("approach", "")}
Execution Steps: {", ".join(plan_steps)}
Success Criteria: {", ".join(success_criteria)}
Potential Issues: {", ".join(potential_issues)}
User Request: {user_request}
Domain: {domain}

Artifact: {artifact_url[:100]}... (truncated)

Please review this artifact against the work plan."""

        try:
            result = self.llm.complete(prompt=prompt, temperature=0.2, max_tokens=1000, system_prompt=system_prompt)
            content = result.get("content", "")

            if "{" in content and "}" in content:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                json_str = content[json_start:json_end]
                review_data = json.loads(json_str)

                return {
                    "success": True,
                    "approved": review_data.get("approved", False),
                    "feedback": review_data.get("feedback", ""),
                    "issues": review_data.get("issues", []),
                    "criteria_met": review_data.get("criteria_met", []),
                    "criteria_not_met": review_data.get("criteria_not_met", []),
                    "plan_adherence": review_data.get("plan_adherence", "medium"),
                    "reviewed_at": datetime.now(timezone.utc).isoformat(),
                }

            return {"success": True, "approved": True, "feedback": "", "issues": [], "plan_adherence": "unknown"}

        except Exception as e:
            return {"success": False, "approved": True, "error": str(e)}

    def regenerate_with_feedback(
        self,
        work_plan: dict[str, Any],
        review_feedback: str,
        csv_data: str,
        domain: str,
    ) -> dict[str, Any]:
        """Regenerate artifact based on review feedback."""
        system_prompt = f"""You are an expert {domain} data analyst. The previous artifact was rejected:

{review_feedback}

Your task is to regenerate the artifact to address these issues while following the work plan.

Generate a new approach. Return a JSON object with:
{{
    "revised_approach": "Description of changes to make",
    "new_steps": ["Step 1", "Step 2"],
    "code_or_instructions": "Any specific code changes needed"
}}"""

        prompt = f"""Original User Request: {work_plan.get("user_request", "")}
Domain: {domain}

Please revise the approach to address the review feedback."""

        try:
            result = self.llm.complete(prompt=prompt, temperature=0.3, max_tokens=1000, system_prompt=system_prompt)
            content = result.get("content", "")

            if "{" in content and "}" in content:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                json_str = content[json_start:json_end]
                revision = json.loads(json_str)
                return {"success": True, "revision": revision}

            return {"success": False, "error": "Failed to parse revision"}

        except Exception as e:
            return {"success": False, "error": str(e)}
