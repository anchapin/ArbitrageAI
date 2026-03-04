"""
Learning and experience logging module.

This module contains experience vector database integration,
arena learning logging, and closed-loop learning functionality.
"""


from src.utils.logger import get_logger

# Import Experience Vector Database for few-shot learning (RAG)
try:
    from src.experience_vector_db import store_successful_task
    EXPERIENCE_DB_AVAILABLE = True
except ImportError:
    EXPERIENCE_DB_AVAILABLE = False

logger = get_logger(__name__)


class ExperienceLogger:
    """Logger for storing successful task experiences."""

    @staticmethod
    def log_success(task) -> None:
        """Log a successful task completion."""
        if not EXPERIENCE_DB_AVAILABLE:
            return

        try:
            # Extract the generated code from execution log if available
            generated_code = ""
            if hasattr(task, "execution_log") and task.execution_log:
                plan_exec = task.execution_log.get("plan_execution", {})
                if plan_exec.get("result", {}).get("code"):
                    generated_code = plan_exec["result"]["code"]

            if generated_code:
                # Store the experience for future few-shot learning
                csv_headers = []
                csv_data = getattr(task, "csv_data", None)
                if csv_data:
                    first_line = csv_data.strip().split("\n")[0]
                    csv_headers = [h.strip() for h in first_line.split(",")]

                store_successful_task(
                    task_id=getattr(task, "id", ""),
                    user_request=getattr(task, "description", ""),
                    generated_code=generated_code,
                    domain=getattr(task, "domain", ""),
                    task_type="visualization",
                    output_format=getattr(task, "result_type", "image"),
                    csv_headers=csv_headers,
                )
                logger.info("Stored experience for few-shot learning")
        except Exception as e:
            logger.error(f"Error logging task success: {e}", exc_info=True)


class ArenaLearningLogger:
    """Logger for arena competition results."""

    @staticmethod
    def log_winner(arena_result: dict, task_data: dict) -> None:
        """Log the winning agent from an arena competition."""
        try:
            from src.agent_execution.arena import ArenaLearningLogger as ArenaLogger
            arena_logger = ArenaLogger()
            arena_logger.log_winner(arena_result, task_data)
        except Exception as e:
            logger.error(f"Error logging arena winner: {e}", exc_info=True)

    @staticmethod
    def log_loser(arena_result: dict, task_data: dict) -> None:
        """Log the losing agent from an arena competition."""
        try:
            from src.agent_execution.arena import ArenaLearningLogger as ArenaLogger
            arena_logger = ArenaLogger()
            arena_logger.log_loser(arena_result, task_data)
        except Exception as e:
            logger.error(f"Error logging arena loser: {e}", exc_info=True)


async def _log_arena_learning(
    arena_result: dict, task_id: str, domain: str, user_request: str,
) -> None:
    """Log arena results to learning systems."""
    try:
        arena_logger = ArenaLearningLogger()
        task_data = {"id": task_id, "domain": domain, "description": user_request}
        arena_logger.log_winner(arena_result, task_data)
        arena_logger.log_loser(arena_result, task_data)
        logger.info(f"Learning data logged for task {task_id}")
    except (FileNotFoundError, OSError) as e:
        logger.error(f"Error logging learning data (file I/O): {e}", exc_info=True)
    except (KeyError, TypeError, ValueError) as e:
        logger.error(f"Error logging learning data (data error): {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error logging learning data: {e}", exc_info=True)


# Convenience functions for backward compatibility
experience_logger = ExperienceLogger()


__all__ = [
    "EXPERIENCE_DB_AVAILABLE",
    "ArenaLearningLogger",
    "ExperienceLogger",
    "_log_arena_learning",
    "experience_logger",
]
