import os
import time
import html
import logging
from datetime import datetime, timezone

from src.generate_fact import generate_fact
from src.send_news import execute_and_send_news
from src.db import log_request, get_eligible_user_ids
from src.telegram_utils import send_telegram_message

logger = logging.getLogger("schedulers")


def execute_fact_scheduler() -> tuple[int, dict]:
    """
    Executes the daily fact scheduler: generates a fact, sends it to all eligible Telegram users, and logs requests.
    Returns (status_code, response_json).
    """
    start_time = time.time()
    logger.info("Starting execute_fact_scheduler")

    eligible_user_ids = get_eligible_user_ids()
    if not eligible_user_ids:
        err_msg = "No eligible users found for scheduler execution."
        logger.error(err_msg)
        log_request(
            endpoint="fact_scheduler",
            status="error",
            error_message=err_msg,
            execution_time_ms=int((time.time() - start_time) * 1000)
        )
        return 500, {"error": err_msg}

    try:
        insight_content, seed, insight_type = generate_fact(return_topic=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        message = f"{insight_content}\n\n<i>{timestamp}</i>"

        sent_count = 0
        failed_count = 0

        for chat_id in eligible_user_ids:
            try:
                send_telegram_message(chat_id, message)
                sent_count += 1
                log_request(
                    endpoint="fact_scheduler",
                    status="success",
                    chat_id=chat_id,
                    command="scheduler_run",
                    response_content=message,
                    topic=seed,
                    execution_time_ms=int((time.time() - start_time) * 1000)
                )
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to send fact to user {chat_id}: {e}")
                log_request(
                    endpoint="fact_scheduler",
                    status="error",
                    chat_id=chat_id,
                    command="scheduler_run",
                    error_message=str(e),
                    execution_time_ms=int((time.time() - start_time) * 1000)
                )

        logger.info(f"Fact scheduler complete: sent to {sent_count}/{len(eligible_user_ids)} users (failed: {failed_count}).")
        return 200, {
            "ok": True,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "total_eligible": len(eligible_user_ids)
        }
    except Exception as e:
        logger.exception("Error during daily fact scheduler invocation")
        log_request(
            endpoint="fact_scheduler",
            status="error",
            command="scheduler_run",
            error_message=str(e),
            execution_time_ms=int((time.time() - start_time) * 1000)
        )
        return 500, {"error": str(e)}


def execute_news_scheduler(query_params: dict) -> tuple[int, dict]:
    """
    Executes the daily news scheduler: queries Talivy, sends digests to all eligible Telegram users, and logs requests.
    Returns (status_code, response_json).
    """
    start_time = time.time()
    logger.info("Starting execute_news_scheduler")

    eligible_user_ids = get_eligible_user_ids()
    if not eligible_user_ids:
        err_msg = "No eligible users found for scheduler execution."
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
            chat_id=eligible_user_ids,
            query=query,
            limit=limit,
            summary=summary
        )
        response_content = "\n\n---\n\n".join(sent_texts)
        mode = "summary" if summary else "batch"

        for chat_id in eligible_user_ids:
            log_request(
                endpoint="news_scheduler",
                status="success",
                chat_id=chat_id,
                command=command_desc,
                response_content=response_content,
                topic=final_query,
                execution_time_ms=int((time.time() - start_time) * 1000)
            )

        logger.info(f"News scheduler complete: sent to {len(eligible_user_ids)} users.")
        return 200, {
            "ok": True,
            "mode": mode,
            "results": count,
            "total_eligible": len(eligible_user_ids)
        }
    except Exception as e:
        logger.exception("Error during daily news scheduler invocation")
        log_request(
            endpoint="news_scheduler",
            status="error",
            command=command_desc,
            error_message=str(e),
            execution_time_ms=int((time.time() - start_time) * 1000)
        )
        return 500, {"error": str(e)}

