from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_or_create_user
from config import STORE_NAME
from utils.permissions import get_cargo_db
import time


START_COOLDOWN_SECONDS = 2.0


def main_menu_caption() -> str:
    return (
        f"🏪 *Bem-vindo à {STORE_NAME}!*\n\n"
        "Escolha uma opção no menu abaixo:"
    )


def build_main_menu_markup(user_id: int) -> InlineKeyboardMarkup:
    """Teclado do menu inicial (reutilizado após PIX confirmado etc.)."""
    teclado = [
        [
            InlineKeyboardButton("🛒 Comprar", callback_data="comprar_menu"),
            InlineKeyboardButton("🔴 Combo GG", callback_data="combo_gg"),
        ],
        [
            InlineKeyboardButton("🎰 Cassino", callback_data="cassino"),
            InlineKeyboardButton("💳 PIX", callback_data="pix_menu"),
        ],
        [InlineKeyboardButton("👤 Perfil", callback_data="perfil_menu")],
    ]
    if get_cargo_db(user_id) is not None:
        teclado.append([InlineKeyboardButton("🛠 Painel Admin", callback_data="adm_menu")])
    return InlineKeyboardMarkup(teclado)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    now = time.monotonic()
    last_start = context.user_data.get("_last_start_ts", 0.0)

    # Evita spam de /start/menu em cliques repetidos.
    if now - last_start < START_COOLDOWN_SECONDS:
        if query:
            await query.answer("Aguarde 2 segundos antes de repetir.", show_alert=False)
        return

    context.user_data["_last_start_ts"] = now

    user = update.effective_user
    ref_id = None
    if not query:
        args = context.args or []
        if args and args[0].isdigit() and int(args[0]) != user.id:
            ref_id = int(args[0])

    if query:
        await query.answer()

    # Registra/atualiza usuário em todo acesso ao menu (callback ou /start com ref)
    get_or_create_user(user.id, user.username, ref_id)

    markup = build_main_menu_markup(user.id)
    texto = main_menu_caption()

    if query:
        await query.edit_message_text(texto, reply_markup=markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(texto, reply_markup=markup, parse_mode="Markdown")
