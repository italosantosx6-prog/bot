import logging
import threading

from config import SUPABASE_URL, SUPABASE_ANON_KEY

logger = logging.getLogger(__name__)

REALTIME_TABLES = [
    "users",
    "ggs",
    "ccs",
    "logins",
    "gift_codes",
    "historico",
    "pagamentos",
]


def _handle_realtime(payload: dict):
    table = payload.get("table") or payload.get("schema")
    event = payload.get("event")
    record = payload.get("record") or payload.get("new") or payload.get("old")
    logger.info("[Supabase Realtime] event=%s table=%s payload=%s", event, table, record)


def _run_realtime_listener() -> None:
    if not SUPABASE_ANON_KEY:
        logger.warning("Supabase realtime listener disabled: SUPABASE_ANON_KEY not configured.")
        return

    try:
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

        for table in REALTIME_TABLES:
            try:
                client.channel(f"public:{table}") \
                    .on_postgres_changes("*", schema="public", table=table, callback=_handle_realtime) \
                    .subscribe()
                logger.info("[Supabase Realtime] subscribed to table=%s", table)
            except Exception as exc:
                logger.exception("Failed to subscribe to table %s: %s", table, exc)

        logger.info("[Supabase Realtime] all channels subscribed.")
    except Exception as exc:
        logger.exception("Supabase realtime listener failed: %s", exc)


def start_realtime_listener() -> None:
    thread = threading.Thread(
        target=_run_realtime_listener,
        daemon=True,
        name="SupabaseRealtimeListener",
    )
    thread.start()
    logger.info("Supabase realtime listener thread started.")
