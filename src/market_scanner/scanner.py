"""
Market Scanner Module.

Scans freelance marketplaces for potential tasks using Playwright.
"""

from datetime import datetime
import json
import os
from pathlib import Path
import re
from typing import Any

from dotenv import load_dotenv

from src.utils.logger import get_logger

from .models import EvaluationResult, JobPosting

load_dotenv()
logger = get_logger(__name__)

# Configuration
MARKETPLACES_FILE = os.environ.get(
    "MARKETPLACES_FILE",
    str(Path(__file__).parent / "../../data/marketplaces.json"),
)
DEFAULT_MARKETPLACE_URL = "https://example.com/freelance-jobs"
EVALUATION_MODEL = os.environ.get("MARK_SCAN_MODEL", "llama3.2")


def get_max_bid_amount() -> int:
    """Get MAX_BID_AMOUNT from ConfigManager."""
    try:
        from src.config.config_manager import ConfigManager
        return ConfigManager.get("BID_LIMIT_CENTS") // 100
    except Exception:
        return 400


def get_min_bid_amount() -> int:
    """Get MIN_BID_AMOUNT from ConfigManager."""
    try:
        from src.config.config_manager import ConfigManager
        return ConfigManager.get("MIN_BID_AMOUNT") // 100
    except Exception:
        return 30


def get_page_load_timeout() -> int:
    """Get PAGE_LOAD_TIMEOUT from ConfigManager."""
    try:
        from src.config.config_manager import ConfigManager
        return ConfigManager.get("MARKET_SCAN_PAGE_TIMEOUT", 30)
    except Exception:
        return 30


def get_scan_interval() -> int:
    """Get SCAN_INTERVAL from ConfigManager."""
    try:
        from src.config.config_manager import ConfigManager
        return ConfigManager.get("MARKET_SCAN_INTERVAL", 60)
    except Exception:
        return 60


def is_training_mode() -> bool:
    """Check if system is running in training mode."""
    try:
        from src.config.config_manager import ConfigManager
        return ConfigManager.get("TRAINING_MODE", False)
    except Exception:
        return False


MAX_BID_AMOUNT = get_max_bid_amount()
MIN_BID_AMOUNT = get_min_bid_amount()
PAGE_LOAD_TIMEOUT = get_page_load_timeout()
SCAN_INTERVAL = get_scan_interval()


class MarketScanner:
    """Scans freelance marketplaces for potential tasks."""

    def __init__(
        self,
        marketplace_url: str | None = None,
        headless: bool = True,
        timeout: int = PAGE_LOAD_TIMEOUT,
    ):
        """Initialize the MarketScanner."""
        self.marketplace_urls: list[str] = []
        self.marketplace_url = marketplace_url
        self.headless = headless
        self.timeout = timeout * 1000

        self.playwright = None
        self.browser = None
        self.page = None
        self.llm = None

        self._load_marketplaces_from_config()
        self._init_llm()

    def _load_marketplaces_from_config(self) -> None:
        """Load active marketplace URLs from config."""
        try:
            if not Path(MARKETPLACES_FILE).exists():
                logger.warning(f"Marketplaces config file not found: {MARKETPLACES_FILE}")
                self.marketplace_urls = [DEFAULT_MARKETPLACE_URL]
                return

            with open(MARKETPLACES_FILE, encoding="utf-8") as f:
                data = json.load(f)

            marketplaces = data.get("marketplaces", [])
            self.marketplace_urls = [
                m["url"] for m in marketplaces if m.get("is_active", True) and m.get("url")
            ]

            if not self.marketplace_urls:
                logger.warning("No active marketplaces found in config, using default")
                self.marketplace_urls = [DEFAULT_MARKETPLACE_URL]

            logger.info(f"Loaded {len(self.marketplace_urls)} marketplace URLs from config")

        except (json.JSONDecodeError, ValueError, FileNotFoundError, OSError, KeyError, TypeError) as e:
            logger.error(f"Failed to load marketplaces from config: {e}", exc_info=True)
            self.marketplace_urls = [DEFAULT_MARKETPLACE_URL]
        except Exception as e:
            logger.error(f"Failed to load marketplaces from config: {e}", exc_info=True)
            self.marketplace_urls = [DEFAULT_MARKETPLACE_URL]

    def _init_llm(self):
        """Initialize LLM service for evaluation."""
        try:
            from src.llm_service import LLMService
            self.llm = LLMService.with_local(model=EVALUATION_MODEL)
            logger.info(f"MarketScanner initialized with LLM model: {EVALUATION_MODEL}")
        except Exception as e:
            logger.warning(f"Failed to initialize LLM service: {e}", exc_info=True)

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
        return False

    async def start(self):
        """Start the Playwright browser."""
        try:
            await self.stop()
            from .browser_pool import get_browser_pool
            pool = get_browser_pool()
            try:
                await pool.start()
            except Exception as e:
                logger.warning(f"BrowserPool start warning: {e}", exc_info=True)
            self.browser = await pool.acquire_browser()
            logger.info("MarketScanner started successfully using BrowserPool")
        except Exception as e:
            logger.error(f"Failed to start scanner: {e}", exc_info=True)
            await self.stop()
            raise

    async def stop(self):
        """Stop the Playwright browser and cleanup."""
        try:
            if self.page:
                try:
                    await self.page.close()
                except Exception as e:
                    logger.warning(f"Error closing page: {e}", exc_info=True)

            if self.browser:
                from .browser_pool import get_browser_pool
                pool = get_browser_pool()
                await pool.release_browser(self.browser)

            logger.info("MarketScanner resources released back to pool")
        except Exception as e:
            logger.warning(f"Error releasing MarketScanner resources: {e}", exc_info=True)
        finally:
            self.page = None
            self.browser = None
            self.playwright = None

    async def fetch_job_postings(
        self, max_posts: int = 10, marketplace_url: str | None = None,
    ) -> list[JobPosting]:
        """Fetch job postings from the marketplace."""
        if not self.browser:
            await self.start()

        url = marketplace_url or self.marketplace_url or (
            self.marketplace_urls[0] if self.marketplace_urls else DEFAULT_MARKETPLACE_URL
        )

        job_postings = []
        page = None

        try:
            page = await self.browser.new_page()
            await page.set_default_timeout(self.timeout)

            logger.info(f"Navigating to marketplace: {url}")
            response = await page.goto(url, wait_until="domcontentloaded")

            if response and response.status >= 400:
                logger.warning(f"Marketplace returned status {response.status}")
                return self._get_mock_job_postings(max_posts)

            await page.wait_for_load_state("networkidle", timeout=self.timeout)

            job_elements = await page.query_selector_all([
                ".job-listing", ".job-card", ".freelancer-project", ".project-card",
                "[data-testid='job-post']", ".listing-item", "article.job", ".job-post",
            ])

            if not job_elements:
                logger.warning("No job postings found with common selectors")
                return self._get_mock_job_postings(max_posts)

            for i, element in enumerate(job_elements[:max_posts]):
                try:
                    posting = await self._extract_job_posting(element, i)
                    if posting:
                        job_postings.append(posting)
                except Exception as e:
                    logger.warning(f"Failed to extract job posting {i}: {e}", exc_info=True)
                    continue

            logger.info(f"Extracted {len(job_postings)} job postings")

        except Exception as e:
            logger.error(f"Error fetching job postings: {e}", exc_info=True)
            return self._get_mock_job_postings(max_posts)

        finally:
            if page:
                try:
                    await page.close()
                except Exception as e:
                    logger.warning(f"Error closing page during cleanup: {e}", exc_info=True)

        return job_postings

    @staticmethod
    async def _extract_job_posting(element, index: int) -> JobPosting | None:
        """Extract job posting data from a page element."""
        try:
            title_elem = await element.query_selector(["h2", "h3", ".title", ".job-title"])
            title = await title_elem.inner_text() if title_elem else f"Job {index + 1}"

            desc_elem = await element.query_selector([".description", ".job-description", ".snippet", "p"])
            description = await desc_elem.inner_text() if desc_elem else ""

            budget_elem = await element.query_selector([".budget", ".price", ".amount", ".job-price"])
            budget = await budget_elem.inner_text() if budget_elem else None

            skill_elems = await element.query_selector_all([".skills span", ".skill-tag", ".tag"])
            skills = []
            for skill in skill_elems:
                skill_text = await skill.inner_text()
                if skill_text:
                    skills.append(skill_text.strip())

            link_elem = await element.query_selector("a")
            url = await link_elem.get_attribute("href") if link_elem else None

            return JobPosting(
                title=title.strip(),
                description=description.strip()[:500],
                budget=budget,
                skills=skills,
                url=url,
            )

        except Exception as e:
            logger.warning(f"Failed to extract job posting: {e}", exc_info=True)
            return None

    @staticmethod
    def _get_mock_job_postings(max_posts: int) -> list[JobPosting]:
        """Get mock job postings for testing."""
        mock_postings = [
            JobPosting(
                title="Python Data Analysis Script",
                description="Need a Python developer to create a data analysis script.",
                budget="$100-200",
                skills=["Python", "pandas", "matplotlib"],
            ),
            JobPosting(
                title="React Dashboard Development",
                description="Looking for an experienced React developer.",
                budget="$500-1000",
                skills=["React", "JavaScript", "D3.js"],
            ),
            JobPosting(
                title="Excel Spreadsheet Automation",
                description="Need VBA macros created to automate tasks.",
                budget="$50-150",
                skills=["Excel", "VBA"],
            ),
        ]
        return mock_postings[:max_posts]

    async def evaluate_post(self, title: str, description: str) -> EvaluationResult:
        """Evaluate a job posting for suitability."""
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(title) % 10000}"

        if self.llm:
            return await self._evaluate_with_llm(title, description, task_id)

        return self._evaluate_fallback(title, description, task_id)

    async def _evaluate_with_llm(self, title: str, description: str, task_id: str) -> EvaluationResult:
        """Evaluate job posting using local LLM."""
        system_prompt = """You are an expert freelance job evaluator.
Return ONLY valid JSON with these keys:
{
    "is_suitable": true or false,
    "bid_amount": integer,
    "reasoning": "Brief explanation",
    "confidence": float between 0 and 1
}"""

        prompt = f"""Job Title: {title}
Job Description: {description}

Evaluate this job posting and return JSON."""

        try:
            result = self.llm.complete(prompt=prompt, system_prompt=system_prompt, temperature=0.3, max_tokens=500)
            response_content = result.get("content", "{}")

            json_match = re.search(r"\{[\s\S]*\}", response_content)
            if json_match:
                eval_data = json.loads(json_match.group(0))
                bid_amount = int(eval_data.get("bid_amount", 50))
                bid_amount = max(MIN_BID_AMOUNT, min(MAX_BID_AMOUNT, bid_amount))

                return EvaluationResult(
                    is_suitable=eval_data.get("is_suitable", False),
                    bid_amount=bid_amount,
                    reasoning=eval_data.get("reasoning", "Evaluation completed"),
                    task_id=task_id,
                    confidence=eval_data.get("confidence", 0.5),
                )

            return self._evaluate_fallback(title, description, task_id)

        except Exception as e:
            logger.error(f"LLM evaluation failed: {e}", exc_info=True)
            return self._evaluate_fallback(title, description, task_id)

    @staticmethod
    def _evaluate_fallback(title: str, description: str, task_id: str) -> EvaluationResult:
        """Fallback rule-based evaluation."""
        title_lower = title.lower()
        desc_lower = description.lower()

        suitable_keywords = [
            "python", "data", "analysis", "excel", "spreadsheet", "chart",
            "visualization", "report", "document", "script", "automation",
        ]

        unsuitable_keywords = [
            "physical", "in-person", "on-site", "video", "call", "meeting",
        ]

        for keyword in unsuitable_keywords:
            if keyword in title_lower or keyword in desc_lower:
                return EvaluationResult(
                    is_suitable=False,
                    bid_amount=50,
                    reasoning=f"Job contains '{keyword}' which requires human involvement.",
                    task_id=task_id,
                    confidence=0.9,
                )

        suitable_count = sum(1 for kw in suitable_keywords if kw in title_lower or kw in desc_lower)

        if suitable_count >= 1:
            base_bid = 50
            if len(description) > 300:
                base_bid += 25

            return EvaluationResult(
                is_suitable=True,
                bid_amount=base_bid,
                reasoning=f"Job appears suitable ({suitable_count} matching keywords).",
                task_id=task_id,
                confidence=0.6,
            )

        return EvaluationResult(
            is_suitable=False,
            bid_amount=50,
            reasoning="Job does not match typical AI-capable tasks.",
            task_id=task_id,
            confidence=0.5,
        )

    async def scan_and_evaluate(
        self,
        max_posts: int = 10,
        min_bid_threshold: int = 30,
        marketplace_url: str | None = None,
    ) -> dict[str, Any]:
        """Scan marketplace and evaluate all job postings."""
        start_time = datetime.now()

        try:
            postings = await self.fetch_job_postings(max_posts, marketplace_url=marketplace_url)

            if not postings:
                return {"success": False, "message": "No job postings found", "postings": [], "evaluations": []}

            evaluations = []
            suitable_jobs = []

            for posting in postings:
                evaluation = await self.evaluate_post(posting.title, posting.description)
                evaluation.task_id = f"{evaluation.task_id}_{hash(posting.title) % 1000}"
                evaluations.append(evaluation.to_dict())

                if evaluation.is_suitable and evaluation.bid_amount >= min_bid_threshold:
                    suitable_jobs.append({
                        "posting": {
                            "title": posting.title,
                            "description": posting.description[:200] + "...",
                            "url": posting.url,
                            "budget": posting.budget,
                            "skills": posting.skills,
                        },
                        "evaluation": evaluation.to_dict(),
                        "bid_placed": False,
                    })

            scan_duration = (datetime.now() - start_time).total_seconds()

            return {
                "success": True,
                "message": f"Scanned {len(postings)} postings, found {len(suitable_jobs)} suitable",
                "postings_count": len(postings),
                "suitable_count": len(suitable_jobs),
                "suitable_jobs": suitable_jobs,
                "all_evaluations": evaluations,
                "scan_duration_seconds": scan_duration,
                "scanned_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Scan and evaluation failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Scan failed: {e!s}",
                "postings": [],
                "evaluations": [],
                "error": str(e),
            }


async def run_single_scan(
    marketplace_url: str | None = None, max_posts: int = 10,
) -> dict[str, Any]:
    """Run a single market scan."""
    async with MarketScanner(marketplace_url=marketplace_url) as scanner:
        return await scanner.scan_and_evaluate(max_posts=max_posts)
