import logging
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes
from database.db import get_gift_code, marcar_gift_code_usado, update_saldo, get_user, is_user_banned

logger = logging.getLogger(__name__)


def _parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


async def gift_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_user_banned(user_id):
        await update.message.reply_text("🚫 Você está banido e não pode usar o bot.")
        return

    args = context.args or []
    if not args:
        await update.message.reply_text(
            "🎁 *Resgatar Gift*\n\n"
            "Use /resgatar <código> ou /gift <código> para resgatar o gift exclusivo enviado pelo admin.\n"
            "Ex: `/resgatar ABC123XYZ`",
            parse_mode="Markdown"
        )
        return

    code = args[0].strip().upper()
    gift = get_gift_code(code)
    if not gift:
        await update.message.reply_text("❌ Gift não encontrado ou inválido.")
        return

    if gift.get("used"):
        await update.message.reply_text("❌ Este gift já foi usado.")
        return

    if gift.get("telegram_id") not in (0, user_id):
        await update.message.reply_text("❌ Este gift não é para você.")
        return

    expires_at = _parse_datetime(gift.get("expires_at"))
    if expires_at and datetime.now(timezone.utc) > expires_at:
        await update.message.reply_text("❌ Este gift expirou.")
        return

    valor = float(gift.get("valor") or 0)
    if valor <= 0:
        await update.message.reply_text("❌ Gift inválido. Valor incorreto.")
        return

    update_saldo(user_id, valor)
    marcar_gift_code_usado(code, user_id)
    user = get_user(user_id)
    await update.message.reply_text(
        "✅ Gift resgatado com sucesso!\n\n"
        f"💰 Valor: R$ {valor:.2f}\n"
        f"💼 Saldo atual: R$ {user['saldo']:.2f}",
        parse_mode="Markdown"
    )
