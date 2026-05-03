"""
handlers/perfil.py
Exibe o perfil do usuário: saldo, comissão, histórico, link de afiliado.
"""
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_user, historico_usuario, trocar_comissao_por_saldo
from config import BOT_USERNAME


def _perfil_texto(user: dict) -> str:
    agora = datetime.now()
    return (
        f"🏆 *SEU PERFIL*\n"
        f"👤 Nome: {user.get('username') or '.'}\n"
        f"🆔 ID: `{user['telegram_id']}`\n\n"
        f"📅 *DATA ATUAL*\n"
        f"📆 Data: {agora.strftime('%d/%m/%Y')}\n"
        f"🕐 Hora: {agora.strftime('%H:%M:%S')}\n\n"
        f"🛍️ *LINK AFILIADO*\n"
        f"💰 Convide pessoas com seu link e ganhe pontos por indicação "
        f"ou a cada recarga feita por ele.\n"
        f"🛍️ Link Afiliado: https://t.me/{BOT_USERNAME}?start={user['telegram_id']}\n\n"
        f"✨ ID: {user['telegram_id']}\n"
        f"🌙 Saldo: R$ {user['saldo']:.2f}\n"
        f"💸 Comissão: R$ {user['comissao']:.2f}"
    )


MENU_PERFIL = [
    [
        InlineKeyboardButton("📋 Histórico Auxiliar", callback_data="perfil_hist_aux"),
        InlineKeyboardButton("📋 Histórico Logins", callback_data="perfil_hist_logins"),
    ],
    [InlineKeyboardButton("⚜️ Trocar por saldo", callback_data="perfil_trocar_comissao")],
    [
        InlineKeyboardButton("📋 Histórico Full", callback_data="perfil_hist_full"),
        InlineKeyboardButton("« Voltar", callback_data="menu_principal"),
    ],
]


async def perfil_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("❌ Usuário não encontrado. Use /start")
        return
    await update.message.reply_text(
        _perfil_texto(user),
        reply_markup=InlineKeyboardMarkup(MENU_PERFIL),
        parse_mode="Markdown"
    )


async def perfil_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if data == "perfil_menu":
        user = get_user(uid)
        if not user:
            await query.edit_message_text("❌ Usuário não encontrado.")
            return
        await query.edit_message_text(
            _perfil_texto(user),
            reply_markup=InlineKeyboardMarkup(MENU_PERFIL),
            parse_mode="Markdown"
        )
        return

    if data == "perfil_trocar_comissao":
        valor = trocar_comissao_por_saldo(uid)
        if valor <= 0:
            await query.answer("❌ Sem comissão para trocar.", show_alert=True)
            return
        user = get_user(uid)
        await query.edit_message_text(
            f"✅ *Comissão convertida!*\n\n"
            f"💰 Adicionado: R$ {valor:.2f}\n"
            f"💼 Saldo atual: R$ {user['saldo']:.2f}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Voltar", callback_data="perfil_menu")]]),
            parse_mode="Markdown"
        )
        return

    if data in ("perfil_hist_full", "perfil_hist_aux", "perfil_hist_logins"):
        historico = historico_usuario(uid)

        if data == "perfil_hist_logins":
            historico = [h for h in historico if h.get("tipo") == "login"]
        elif data == "perfil_hist_aux":
            historico = [h for h in historico if h.get("tipo") in ("ggg", "cc")]

        if not historico:
            await query.answer("📭 Sem registros.", show_alert=True)
            return

        linhas = [f"📋 *Histórico ({len(historico)} itens)*\n"]
        for h in historico[:20]:
            tipo = h.get("tipo", "?").upper()
            val = h.get("valor", 0)
            created = h.get("created_at", "")[:10]
            linhas.append(f"• {tipo} — R$ {val:.2f} — {created}")

        await query.edit_message_text(
            "\n".join(linhas),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Voltar", callback_data="perfil_menu")]]),
            parse_mode="Markdown"
        )
