"""
Montagem dos Applications Telegram — cliente (loja) vs staff (admin).

Ambos usam o mesmo Supabase; os dados são idênticos.

Cliente: `/pix VALOR` (mesma mensagem) + callback do menu PIX.
"""
from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    InlineQueryHandler,
    MessageHandler,
    filters,
)

from config import BOT_TOKEN, ADMIN_BOT_TOKEN, STORE_NAME
from handlers.start import start_handler
from handlers.comprar import comprar_callback
from handlers.ggs import ggs_callback, ggs_busca_handler
from handlers.ccs import ccs_callback, ccs_busca_handler
from handlers.perfil import perfil_callback
from handlers.admin_painel import adm_command, adm_callback, adm_msg_handler
from handlers.inline_search import inline_query_handler
from handlers.gift import gift_handler
from handlers.pix_handler import pix_check_callback, pix_handler, pix_menu_callback
from utils.telegram_errors import telegram_error_handler


async def _adm_denied_on_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cliente não deve usar painel neste bot."""
    await update.message.reply_text(
        "🔒 O painel administrativo fica no *bot de equipe*.\n"
        "Este é apenas o bot da loja.",
        parse_mode="Markdown",
    )


async def _staff_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🛠️ *{STORE_NAME} — Bot de equipe*\n\n"
        "Use /adm para abrir o painel.\n"
        "Os dados são os mesmos do bot da loja (mesmo banco).",
        parse_mode="Markdown",
    )


async def _post_init_client(app: Application):
    """Menu de comandos do bot da loja."""
    await app.bot.set_my_commands([
        BotCommand("start", "Menu da loja"),
        BotCommand("pix", "Use /pix valor na mesma linha (mín. R$10)"),
        BotCommand("resgatar", "Resgatar gift code"),
    ])


def build_client_application() -> Application:
    """Bot público: compras, PIX, perfil, gift, inline — sem painel admin."""
    app = Application.builder().token(BOT_TOKEN).post_init(_post_init_client).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("gift", gift_handler))
    app.add_handler(CommandHandler("resgatar", gift_handler))
    app.add_handler(CommandHandler("adm", _adm_denied_on_client))

    app.add_handler(pix_handler)

    app.add_handler(InlineQueryHandler(inline_query_handler))

    app.add_handler(CallbackQueryHandler(comprar_callback, pattern=r"^(comprar|cassino|combo_gg)"))
    app.add_handler(CallbackQueryHandler(ggs_callback, pattern=r"^ggs_"))
    app.add_handler(CallbackQueryHandler(ccs_callback, pattern=r"^cc_"))
    app.add_handler(CallbackQueryHandler(pix_menu_callback, pattern=r"^pix_menu$"))
    app.add_handler(CallbackQueryHandler(pix_check_callback, pattern=r"^pix_check_"))
    app.add_handler(CallbackQueryHandler(perfil_callback, pattern=r"^perfil_"))
    app.add_handler(CallbackQueryHandler(start_handler, pattern=r"^menu_principal$"))

    app.add_handler(MessageHandler(
        (filters.TEXT | filters.Document.ALL) & ~filters.COMMAND,
        _multiplex_client_text,
    ))
    app.add_error_handler(telegram_error_handler)
    return app


def build_admin_application() -> Application:
    """Bot staff: só /adm e fluxos do painel (callbacks adm_ + mensagens _adm_modo)."""
    if not ADMIN_BOT_TOKEN:
        raise RuntimeError(
            "ADMIN_BOT_TOKEN não configurado. Crie um segundo bot no @BotFather e defina no .env"
        )

    app = Application.builder().token(ADMIN_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", _staff_start))
    app.add_handler(CommandHandler("adm", adm_command))

    app.add_handler(CallbackQueryHandler(adm_callback, pattern=r"^adm_"))

    app.add_handler(MessageHandler(
        (filters.TEXT | filters.Document.ALL) & ~filters.COMMAND,
        _multiplex_admin_text,
    ))
    app.add_error_handler(telegram_error_handler)
    return app


async def _multiplex_client_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (update.message.text or "").strip().lower()

    if texto.startswith(("buscar_banco ", "buscar_bin ", "buscar_bandeira ")):
        await ggs_busca_handler(update, context)
        return

    if texto.startswith(("cc_buscar_banco ", "cc_buscar_bin ", "cc_buscar_bandeira ")):
        await ccs_busca_handler(update, context)
        return

async def _multiplex_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("_adm_modo"):
        await adm_msg_handler(update, context)
        return
