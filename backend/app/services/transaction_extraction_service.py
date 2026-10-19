"""Choose local GLiNER2 or Groq extraction without changing the transaction API."""

import logging
from time import perf_counter

from app.config import settings
from app.schemas.transaction import Transaction

logger = logging.getLogger("uvicorn.error")


class ExtractionUnavailable(ValueError):
    """Input needs clarification or the selected local extractor is unavailable."""


def extract_transactions(message: str) -> list[Transaction]:
    from app.services.llm_service import extract_transactions_groq

    if settings.extraction_provider == "groq":
        return extract_transactions_groq(message)
    started = perf_counter()
    try:
        from app.services.local_extraction_service import extract_local_transactions

        result = extract_local_transactions(message)
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        if settings.gliner2_fallback_to_groq:
            logger.warning("Extraction fallback: provider=gliner2 target=groq reason=%s", type(exc).__name__)
            return extract_transactions_groq(message)
        logger.warning("Local extraction declined: reason=%s", type(exc).__name__)
        raise ExtractionUnavailable(
            "I couldn't reliably extract that entry locally. Please send one transaction "
            "per line with an amount and purpose, for example 'Spent ₹250 on coffee today'."
        ) from exc
    logger.info("Transaction extraction: provider=gliner2 count=%d elapsed_ms=%.1f", len(result), (perf_counter() - started) * 1000)
    return result
