"""Market Scanner Module.

This module provides functionality to scan freelance marketplaces for potential tasks.
"""

import asyncio

from src.utils.logger import get_logger

from .scanner import MarketScanner, run_single_scan

logger = get_logger(__name__)


async def run_continuous_scan(
    interval: int = 60,
    marketplace_url: str | None = None,
    max_posts: int = 10,
    max_iterations: int | None = None,
):
    """Run continuous market scanning at regular intervals."""
    iteration = 0

    while max_iterations is None or iteration < max_iterations:
        iteration += 1
        logger.info(f"Starting scan iteration {iteration}")

        try:
            async with MarketScanner(marketplace_url=marketplace_url) as scanner:
                result = await scanner.scan_and_evaluate(max_posts=max_posts)
                result["iteration"] = iteration
                yield result

        except Exception as e:
            logger.error(f"Scan iteration {iteration} failed: {e}", exc_info=True)
            yield {"success": False, "error": str(e), "iteration": iteration}

        if max_iterations is None or iteration < max_iterations:
            logger.info(f"Waiting {interval} seconds before next scan")
            await asyncio.sleep(interval)


if __name__ == "__main__":

    async def main():
        """Main entry point for testing."""
        logger.info("=" * 60)
        logger.info("Market Scanner - Test Run")
        logger.info("=" * 60)

        logger.info("\nRunning market scan...")
        result = await run_single_scan(max_posts=5)

        logger.info("\nScan Result:")
        logger.info(f"  Success: {result.get('success')}")
        logger.info(f"  Message: {result.get('message')}")
        logger.info(f"  Postings Found: {result.get('postings_count', 0)}")
        logger.info(f"  Suitable Jobs: {result.get('suitable_count', 0)}")

        if result.get("suitable_jobs"):
            logger.info("\nSuitable Jobs:")
            for i, job in enumerate(result["suitable_jobs"], 1):
                logger.info(f"\n  {i}. {job['posting']['title']}")
                logger.info(f"     Bid: ${job['evaluation']['bid_amount']}")

        logger.info(f"\nScan Duration: {result.get('scan_duration_seconds', 0):.2f}s")

    asyncio.run(main())
