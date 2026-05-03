import asyncio
import logging
import os
import threading
from urllib.parse import urlparse, urlunparse, urlencode

import certifi
from realtime import Socket

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


def _format_payload(payload: dict) -> str:
    table = payload.get("table") or payload.get("schema")
    event = payload.get("event")
    record = payload.get("record") or payload.get("new") or payload.get("old")
    return f"Realtime event={event} table={table} payload={record}"


def _handle_realtime(payload: dict):
    logger.info("[Supabase Realtime] %s", _format_payload(payload))


def _subscribe_table(socket: Socket, table: str):
    channel = socket.set_channel(f"realtime:public:{table}")
    channel.on("postgres_changes", _handle_realtime)
    channel.on("*", _handle_realtime)
    channel.join()
    logger.info("[Supabase Realtime] subscribed to table=%s", table)


from urllib.parse import urlparse, urlunparse, urlencode


def _run_realtime_listener() -> None:
    if not SUPABASE_ANON_KEY:
        logger.warning("Supabase realtime listener disabled because SUPABASE_ANON_KEY is not configured.")
        return

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    parsed = urlparse(SUPABASE_URL)
    realtime_url = urlunparse((
        "wss",
        parsed.netloc,
        "/realtime/v1",
        "",
        urlencode({"apikey": SUPABASE_ANON_KEY, "vsn": "1.0.0"}),
        "",
    ))
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    socket = Socket(realtime_url, auto_reconnect=True)
    try:
        socket.connect()
        logger.info("[Supabase Realtime] connected to %s", realtime_url)
    except Exception as exc:
        logger.exception("Failed to connect Supabase realtime: %s", exc)
        return

    for table in REALTIME_TABLES:
        try:
            _subscribe_table(socket, table)
        except Exception as exc:
            logger.exception("Failed to subscribe to realtime table %s: %s", table, exc)

    try:
        socket.listen()
    except Exception as exc:
        logger.exception("Supabase realtime listener stopped unexpectedly: %s", exc)


def start_realtime_listener() -> None:
    thread = threading.Thread(
        target=_run_realtime_listener,
        daemon=True,
        name="SupabaseRealtimeListener",
    )
    thread.start()
    logger.info("Supabase realtime listener thread started.")
