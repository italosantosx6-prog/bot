"""
Tratamento centralizado de erros do python-telegram-bot.
"""
from __future__ import annotations

import logging

from telegram.error import Conflict
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def telegram_error_handler(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error
    if isinstance(err, Conflict):
        logger.warning(
            "Conflito de getUpdates detectado (instancias duplicadas com mesmo token)."
        )
        return

    logger.exception("Erro nao tratado na aplicacao Telegram", exc_info=err)
