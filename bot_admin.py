"""
Infinity Store — Bot de EQUIPE (admin).

Rode em outro processo/terminal: python bot_admin.py

Precisa de ADMIN_BOT_TOKEN no .env (segundo bot no @BotFather).
Mesmo SUPABASE_URL / SUPABASE_KEY / OWNER_ID que o bot cliente.
"""
import logging

from app_setup import build_admin_application
from config import ADMIN_BOT_TOKEN
from utils.single_instance import acquire_process_lock

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
_PROCESS_LOCK_FD = None


def main():
    global _PROCESS_LOCK_FD
    if ADMIN_BOT_TOKEN:
        _PROCESS_LOCK_FD = acquire_process_lock(f"telegram_polling:{ADMIN_BOT_TOKEN}")
        if _PROCESS_LOCK_FD is None:
            logger.error(
                "Outra instancia do bot STAFF ja esta rodando com o mesmo token. "
                "Encerrando para evitar conflito 409 no getUpdates."
            )
            return

    app = build_admin_application()
    logger.info("Infinity Store — bot STAFF (admin) iniciado.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
