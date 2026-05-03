"""
Infinity Store — Bot da LOJA (cliente).

Rode: python bot_client.py
(ou `python bot.py` — mesmo comportamento)

Não registra painel /adm; dados vêm do mesmo Supabase que o bot de equipe.
"""
import asyncio
import logging

from app_setup import build_client_application
from config import BOT_TOKEN
from utils.single_instance import acquire_process_lock
from telegram import Bot

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
_PROCESS_LOCK_FD = None


def main():
    global _PROCESS_LOCK_FD
    _PROCESS_LOCK_FD = acquire_process_lock(f"telegram_polling:{BOT_TOKEN}")
    if _PROCESS_LOCK_FD is None:
        logger.error(
            "Outra instancia do bot CLIENTE ja esta rodando com o mesmo token. "
            "Encerrando para evitar conflito 409 no getUpdates."
        )
        return

    # Remove qualquer webhook ativo antes de iniciar polling
    async def _clear_webhook():
        bot = Bot(BOT_TOKEN)
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.close()

    asyncio.run(_clear_webhook())

    app = build_client_application()
    logger.info("Infinity Store — bot CLIENTE (loja) iniciado.")
    app.run_polling(drop_pending_updates=True, allowed_updates=["message", "callback_query", "inline_query"])


if __name__ == "__main__":
    main()
