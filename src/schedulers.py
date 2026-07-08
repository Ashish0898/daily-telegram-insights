import os
import time
import html
import logging
from datetime import datetime, timezone

from src.generate_fact import generate_fact
from src.send_news import execute_and_send_news
from src.db import log_request
from src.telegram_utils import send_telegram_message

logger = logging.getLogger("schedulers")

TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def execute_fact_scheduler() -> tuple[int, dict]:
    """
    Executes the daily fact scheduler: generates a fact, sends it to the default Telegram chat, and logs the request.
    Returns (status_code, response_json).
    """
    start_time = time.time()
    logger.info("Starting execute_fact_scheduler")

    if not TELEGRAM_CHAT_ID:
        err_msg = "TELEGRAM_CHAT_ID is not set"
        logger.error(err_msg)
        log_request(
            endpoint="fact_scheduler",
            status="error",
            error_message=err_msg,
            execution_time_ms=int((time.time() - start_time) * 1000)
        )
        return 500, {"error": err_msg}

    try:
        fact, seed, insight_type = generate_fact(return_topic=True)
        fact_escaped = html.escape(fact, quote=False)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        header = "<b>🎯 Daily Fact</b>" if insight_type == "fact" else "<b>💡 Daily Quote</b>"
        message = f"{header}\n\n{fact_escaped}\n\n<i>{timestamp}</i>"

        send_telegram_message(int(TELEGRAM_CHAT_ID), message)

        log_request(
            endpoint="fact_scheduler",
            status="success",
            chat_id=int(TELEGRAM_CHAT_ID),
            command="scheduler_run",
            response_content=message,
            topic=seed,
            execution_time_ms=int((time.time() - start_time) * 1000)
        )
        return 200, {"ok": True}
    except Exception as e:
        logger.exception("Error during daily fact scheduler invocation")
        log_request(
            endpoint="fact_scheduler",
            status="error",
            chat_id=int(TELEGRAM_CHAT_ID),
            command="scheduler_run",
            error_message=str(e),
            execution_time_ms=int((time.time() - start_time) * 1000)
        )
        return 500, {"error": str(e)}

def execute_news_scheduler(query_params: dict) -> tuple[int, dict]:
    """
    Executes the daily news scheduler: queries Talivy, sends digests to Telegram, and logs the request.
    Returns (status_code, response_json).
    """
    start_time = time.time()
    logger.info("Starting execute_news_scheduler")

    if not TELEGRAM_CHAT_ID:
        err_msg = "TELEGRAM_CHAT_ID is not set"
        logger.error(err_msg)
        log_request(
            endpoint="news_scheduler",
            status="error",
            error_message=err_msg,
            execution_time_ms=int((time.time() - start_time) * 1000)
        )
        return 500, {"error": err_msg}

    query = query_params.get("query", [None])[0] or os.getenv("NEWS_QUERY")
    limit_str = query_params.get("limit", [None])[0] or os.getenv("NEWS_LIMIT") or "5"
    try:
        limit = int(limit_str)
    except ValueError:
        limit = 5

    summary_str = query_params.get("summary", [None])[0] or os.getenv("NEWS_SUMMARY") or "false"
    summary = summary_str.lower() == "true"

    command_desc = f"query={query}, limit={limit}, summary={summary}"

    try:
        count, final_query, sent_texts = execute_and_send_news(
            chat_id=int(TELEGRAM_CHAT_ID),
            query=query,
            limit=limit,
            summary=summary
        )
        response_content = "\n\n---\n\n".join(sent_texts)
        mode = "summary" if summary else "batch"

        log_request(
            endpoint="news_scheduler",
            status="success",
            chat_id=int(TELEGRAM_CHAT_ID),
            command=command_desc,
            response_content=response_content,
            topic=final_query,
            execution_time_ms=int((time.time() - start_time) * 1000)
        )
        return 200, {"ok": True, "mode": mode, "results": count}
    except Exception as e:
        logger.exception("Error during daily news scheduler invocation")
        log_request(
            endpoint="news_scheduler",
            status="error",
            chat_id=int(TELEGRAM_CHAT_ID),
            command=command_desc,
            error_message=str(e),
            execution_time_ms=int((time.time() - start_time) * 1000)
        )
        return 500, {"error": str(e)}
