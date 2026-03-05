"""Task Execution Handlers.

Specialized handlers for different task types and domains.
"""

from typing import Any

from src.utils.logger import get_logger

from src.agent_execution.models import TaskProfile

logger = get_logger(__name__)


class TaskHandlerBase:
    """Base class for task handlers."""

    async def execute(self, task_profile: TaskProfile, **kwargs) -> dict[str, Any]:
        """Execute a task. To be implemented by subclasses."""
        raise NotImplementedError


class LegalTaskHandler(TaskHandlerBase):
    """Handler for legal domain tasks."""

    async def execute(self, task_profile: TaskProfile, **kwargs) -> dict[str, Any]:
        """Execute legal domain task."""
        from src.llm_service import LLMService

        from .executor import DocumentGenerator

        llm_service = LLMService.for_complex_task()
        generator = DocumentGenerator(
            domain=task_profile.domain,
            llm_service=llm_service,
            output_format=task_profile.output_format,
        )

        result = generator.generate_document(
            user_request=task_profile.user_request,
            csv_data="\n".join([",".join(task_profile.csv_headers), "sample,data"]),
            **kwargs,
        )

        result["model_used"] = "gpt-4o"
        return result


class AccountingTaskHandler(TaskHandlerBase):
    """Handler for accounting domain tasks."""

    async def execute(self, task_profile: TaskProfile, **kwargs) -> dict[str, Any]:
        """Execute accounting domain task."""
        from src.llm_service import LLMService

        from .executor import TaskRouter

        llm_service = LLMService.for_complex_task()
        router = TaskRouter(llm_service=llm_service)

        if task_profile.output_format == "xlsx":
            result = router.route(
                domain=task_profile.domain,
                user_request=task_profile.user_request,
                csv_data="\n".join([",".join(task_profile.csv_headers), "sample,data"]),
                task_type="spreadsheet",
                output_format=task_profile.output_format,
            )
        else:
            result = router.route(
                domain=task_profile.domain,
                user_request=task_profile.user_request,
                csv_data="\n".join([",".join(task_profile.csv_headers), "sample,data"]),
                task_type=task_profile.task_type,
                output_format=task_profile.output_format,
            )

        result["model_used"] = "gpt-4o"
        return result


class VisualizationTaskHandler(TaskHandlerBase):
    """Handler for data visualization tasks."""

    async def execute(self, task_profile: TaskProfile, **kwargs) -> dict[str, Any]:
        """Execute data visualization task."""
        from src.llm_service import LLMService

        from .executor import execute_data_visualization

        llm_service = LLMService.for_basic_admin()

        result = execute_data_visualization(
            csv_data="\n".join([",".join(task_profile.csv_headers), "sample,data"]),
            user_request=task_profile.user_request,
            llm_service=llm_service,
            domain=task_profile.domain,
            **kwargs,
        )

        result["model_used"] = "llama-3.2"
        return result


class DocumentTaskHandler(TaskHandlerBase):
    """Handler for document generation tasks."""

    async def execute(self, task_profile: TaskProfile, **kwargs) -> dict[str, Any]:
        """Execute document generation task."""
        from src.llm_service import LLMService

        from .executor import DocumentGenerator

        llm_service = kwargs.get("llm_service", LLMService())
        generator = DocumentGenerator(
            domain=task_profile.domain,
            llm_service=llm_service,
            output_format=task_profile.output_format,
        )

        result = generator.generate_document(
            user_request=task_profile.user_request,
            csv_data="\n".join([",".join(task_profile.csv_headers), "sample,data"]),
            **kwargs,
        )

        result["model_used"] = llm_service.get_config().get("model", "unknown")
        return result


class SpreadsheetTaskHandler(TaskHandlerBase):
    """Handler for spreadsheet generation tasks."""

    async def execute(self, task_profile: TaskProfile, **kwargs) -> dict[str, Any]:
        """Execute spreadsheet generation task."""
        from src.llm_service import LLMService

        from .executor import OutputFormat, TaskType, execute_task

        llm_service = kwargs.get("llm_service", LLMService())
        exec_kwargs = {k: v for k, v in kwargs.items() if k != "llm_service"}

        result = execute_task(
            domain=task_profile.domain,
            user_request=task_profile.user_request,
            csv_data="\n".join([",".join(task_profile.csv_headers), "sample,data"]),
            task_type=TaskType.SPREADSHEET,
            output_format=OutputFormat.XLSX,
            llm_service=llm_service,
            **exec_kwargs,
        )

        result["model_used"] = llm_service.get_config().get("model", "unknown")
        return result


class ReportTaskHandler(TaskHandlerBase):
    """Handler for report generation tasks."""

    async def execute(self, task_profile: TaskProfile, **kwargs) -> dict[str, Any]:
        """Execute report generation task."""
        from src.llm_service import LLMService

        from .executor import ReportGenerator

        llm_service = kwargs.get("llm_service", LLMService())
        generator = ReportGenerator(
            domain=task_profile.domain,
            llm_service=llm_service,
            report_type="detailed",
        )

        result = generator.generate_report(
            user_request=task_profile.user_request,
            csv_data="\n".join([",".join(task_profile.csv_headers), "sample,data"]),
            **kwargs,
        )

        result["model_used"] = llm_service.get_config().get("model", "unknown")
        return result


class StandardTaskHandler(TaskHandlerBase):
    """Handler for standard tasks using default routing."""

    async def execute(self, task_profile: TaskProfile, **kwargs) -> dict[str, Any]:
        """Execute standard task using default routing."""
        from .executor import TaskRouter

        task_router = TaskRouter()
        result = task_router.route(
            domain=task_profile.domain,
            user_request=task_profile.user_request,
            csv_data="\n".join([",".join(task_profile.csv_headers), "sample,data"]),
            task_type=task_profile.task_type,
            output_format=task_profile.output_format,
            **kwargs,
        )

        result["model_used"] = "standard"
        return result


class HandlerFactory:
    """Factory for creating task handlers."""

    _handlers = {
        "legal_specialist": LegalTaskHandler,
        "accounting_specialist": AccountingTaskHandler,
        "visualization_specialist": VisualizationTaskHandler,
        "document_generator": DocumentTaskHandler,
        "spreadsheet_generator": SpreadsheetTaskHandler,
        "report_generator": ReportTaskHandler,
        "standard_handler": StandardTaskHandler,
    }

    @classmethod
    def get_handler(cls, handler_type: str) -> TaskHandlerBase:
        """Get a handler instance by type."""
        handler_class = cls._handlers.get(handler_type, StandardTaskHandler)
        return handler_class()

    @classmethod
    def register_handler(cls, handler_type: str, handler_class: type[TaskHandlerBase]):
        """Register a new handler type."""
        cls._handlers[handler_type] = handler_class
