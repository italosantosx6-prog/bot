"""
Infinity Store — Bot da LOJA (cliente).

Rode: python bot_client.py
(ou `python bot.py` — mesmo comportamento)

Não registra painel /adm; dados vêm do mesmo Supabase que o bot de equipe.
"""
import logging

from app_setup import build_client_application
from config import BOT_TOKEN
from utils.single_instance import acquire_process_lock

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

    app = build_client_application()
    logger.info("Infinity Store — bot CLIENTE (loja) iniciado.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
