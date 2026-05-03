"""
Infinity Store — Bot da LOJA (cliente).
"""
import asyncio
import logging
import sys
import time

from telegram import Bot
from telegram.error import Conflict

from app_setup import build_client_application
from config import BOT_TOKEN

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def _clear_webhook():
    bot = Bot(BOT_TOKEN)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook removido com sucesso.")
    except Exception as e:
        logger.warning("Erro ao remover webhook: %s", e)
    finally:
        await bot.close()


def main():
    # Aguarda um pouco para garantir que instância anterior encerrou
    time.sleep(3)

    asyncio.run(_clear_webhook())

    app = build_client_application()
    logger.info("Bot CLIENTE iniciado.")

    try:
        app.run_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query", "inline_query"],
        )
    except Conflict:
        logger.error("Conflito 409 detectado — outra instância rodando. Encerrando.")
        sys.exit(1)


if __name__ == "__main__":
    main()
