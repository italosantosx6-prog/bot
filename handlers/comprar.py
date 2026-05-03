from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


MENU_COMPRAR = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🔑 GGGs Disponíveis", callback_data="ggs_menu"),
        InlineKeyboardButton("💳 CCs Disponíveis", callback_data="cc_menu"),
    ],
    [InlineKeyboardButton("🔐 Logins", callback_data="ggs_logins")],
    [InlineKeyboardButton("« Voltar", callback_data="menu_principal")],
])


async def comprar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛒 *Comprar*\nEscolha a categoria:", reply_markup=MENU_COMPRAR, parse_mode="Markdown")


async def comprar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "comprar_menu":
        await query.edit_message_text(
            "🛒 *Comprar*\nEscolha a categoria:",
            reply_markup=MENU_COMPRAR,
            parse_mode="Markdown"
        )

    elif query.data == "cassino":
        await query.edit_message_text(
            "🎰 *Cassino*\n\nEm breve disponível!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Voltar", callback_data="menu_principal")]]),
            parse_mode="Markdown"
        )

    elif query.data == "combo_gg":
        await query.edit_message_text(
            "🔴 *Combo GG*\n\nEm breve disponível!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Voltar", callback_data="menu_principal")]]),
            parse_mode="Markdown"
        )
