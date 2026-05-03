import logging
import asyncio
import re
from telegram.error import Conflict
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler
)
from config import BOT_TOKEN, BOT_USERNAME
from handlers.start import start_handler
from handlers.comprar import comprar_handler, comprar_callback
from handlers.ggs import ggs_handler, ggs_callback, ggs_busca_handler
from handlers.ccs import ccs_handler, ccs_callback, ccs_busca_handler
from handlers.pix_handler import pix_command, pix_menu_callback, pix_check_callback, pix_amount_select_callback
from handlers.perfil import perfil_handler, perfil_callback
from handlers.gift import gift_handler
from handlers.admin_painel import adm_command, adm_callback, adm_msg_handler
from database.realtime import start_realtime_listener

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Estados de conversa
(
    AGUARDANDO_VALOR_PIX,
    AGUARDANDO_CARD_CHK,
    AGUARDANDO_BUSCA_BANCO,
    AGUARDANDO_BUSCA_BIN,
    AGUARDANDO_BUSCA_BANDEIRA,
    AGUARDANDO_ADD_GGG,
    AGUARDANDO_ADD_CC,
    AGUARDANDO_ADD_LOGIN,
    AGUARDANDO_ADMIN_MSG,
) = range(9)


def main():
    start_realtime_listener()
    asyncio.set_event_loop(asyncio.new_event_loop())

    app = Application.builder().token(BOT_TOKEN).build()

    # /start
    app.add_handler(CommandHandler("start", start_handler))

    # Comprar menu
    app.add_handler(CallbackQueryHandler(comprar_callback, pattern="^comprar"))

    # GGs
    app.add_handler(CallbackQueryHandler(ggs_callback, pattern="^ggs"))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r"^buscar_(banco|bin|bandeira)\s"),
        ggs_busca_handler
    ))
    # Removido handler genérico de busca para GGs — utiliza apenas o comando específico

    # CCs
    app.add_handler(CallbackQueryHandler(ccs_callback, pattern="^cc"))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r"^cc_buscar_(banco|bin|bandeira)\s"),
        ccs_busca_handler
    ))
    # Removido handler genérico de busca para CCs — utiliza apenas o comando específico

    # PIX
    app.add_handler(CallbackQueryHandler(pix_menu_callback, pattern="^pix_menu$"))
    app.add_handler(CallbackQueryHandler(pix_amount_select_callback, pattern="^pix_amount_"))
    app.add_handler(CommandHandler("pix", pix_command))
    app.add_handler(CallbackQueryHandler(pix_check_callback, pattern="^pix_check_"))

    # Perfil
    app.add_handler(CallbackQueryHandler(perfil_callback, pattern="^perfil"))

    # Gift / resgatar
    app.add_handler(CommandHandler("gift", gift_handler))
    app.add_handler(CommandHandler("resgatar", gift_handler))

    # Admin
    app.add_handler(CommandHandler("admin", adm_command))
    app.add_handler(CallbackQueryHandler(adm_callback, pattern="^adm_"))
    # Custom handler: capture amount when user selected "Outro valor"
    from handlers.pix_handler import handle_custom_amount_message
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_custom_amount_message,
    ))

    # Admin message handler (runs after custom amount handler)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        adm_msg_handler
    ))

    # Callback geral (voltar, menu)
    app.add_handler(CallbackQueryHandler(start_handler, pattern="^menu_principal$"))

    async def error_handler(update, context):
        logger.error("Update caused error: %s", context.error, exc_info=context.error)

    app.add_error_handler(error_handler)

    logger.info("🤖 Bot iniciado!")
    try:
        app.run_polling(drop_pending_updates=True, allowed_updates=["message", "callback_query"])
    except Conflict as exc:
        logger.error(
            "Polling conflict detected: %s", exc
        )
        logger.error(
            "Verifique se nenhuma outra instância do bot está rodando com este token."
        )
        raise


if __name__ == "__main__":
    main()
