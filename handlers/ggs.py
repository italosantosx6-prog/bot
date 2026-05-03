"""
handlers/ggs.py
Menu de GGs com Unitária, Mix, Buscar banco/bin/bandeira.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import (
    listar_gggs,
    get_ggg,
    marcar_ggg_vendido_se_disponivel,
    get_user,
    update_saldo,
    registrar_compra,
    debitar_saldo_se_suficiente,
    marcar_login_vendido_se_disponivel,
)
from config import PRECO_GGG_UNITARIA, PRECO_GGG_MIX

MENU_GGS = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🔴 Unitária", callback_data="ggs_unitaria"),
        InlineKeyboardButton("💸 Mix", callback_data="ggs_mix"),
    ],
    [
        InlineKeyboardButton("🏦 Buscar banco »", switch_inline_query_current_chat="buscar_banco "),
        InlineKeyboardButton("🔑 Buscar bin »", switch_inline_query_current_chat="buscar_bin "),
    ],
    [InlineKeyboardButton("🏳 Buscar bandeira »", switch_inline_query_current_chat="buscar_bandeira ")],
    [InlineKeyboardButton("« Voltar", callback_data="comprar_menu")],
])


async def ggs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔑 *GGs*\nEscolha uma opção:", reply_markup=MENU_GGS, parse_mode="Markdown")


async def ggs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "ggs_menu":
        await query.edit_message_text("🔑 *GGs*\nEscolha uma opção:", reply_markup=MENU_GGS, parse_mode="Markdown")
        return

    if data == "ggs_unitaria":
        ggs = listar_gggs()
        if not ggs:
            await query.edit_message_text(
                "😔 Sem GGs disponíveis no momento.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Voltar", callback_data="ggs_menu")]]),
            )
            return

        buttons = []
        for g in ggs[:10]:
            label = f"{g.get('bandeira','?')} | {g.get('banco','?')} | {g.get('bin','?')} — R${PRECO_GGG_UNITARIA:.0f}"
            buttons.append([InlineKeyboardButton(label, callback_data=f"ggs_comprar_{g['id']}")])
        buttons.append([InlineKeyboardButton("« Voltar", callback_data="ggs_menu")])

        texto = f"🔴 *GGs Disponíveis* ({len(ggs)} total)\n\nEscolha um cartão:"
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
        return

    if data == "ggs_mix":
        ggs = listar_gggs()
        total = len(ggs)
        texto = (
            f"💸 *Pacote Mix de GGs*\n\n"
            f"📦 {total} cartões disponíveis\n"
            f"💰 R$ {PRECO_GGG_MIX:.0f} por unidade\n\n"
            f"Quantos deseja comprar?"
        )
        buttons = [
            [InlineKeyboardButton("5 unid.", callback_data="ggs_mix_5"),
             InlineKeyboardButton("10 unid.", callback_data="ggs_mix_10")],
            [InlineKeyboardButton("20 unid.", callback_data="ggs_mix_20"),
             InlineKeyboardButton("50 unid.", callback_data="ggs_mix_50")],
            [InlineKeyboardButton("« Voltar", callback_data="ggs_menu")],
        ]
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
        return

    if data.startswith("ggs_mix_"):
        qtd = int(data.split("_")[-1])
        total = round(qtd * PRECO_GGG_MIX, 2)
        user = get_user(query.from_user.id)
        if not user or user["saldo"] < total:
            await query.answer(f"❌ Saldo insuficiente! Necessário: R$ {total:.2f}", show_alert=True)
            return

        ggs = listar_gggs()[:qtd]
        if len(ggs) < qtd:
            await query.answer(f"❌ Apenas {len(ggs)} disponíveis.", show_alert=True)
            return

        if not debitar_saldo_se_suficiente(query.from_user.id, total):
            await query.answer("❌ Saldo insuficiente ou compra concorrente. Tente novamente.", show_alert=True)
            return
        linhas = []
        for g in ggs:
            if not marcar_ggg_vendido_se_disponivel(g["id"], query.from_user.id):
                continue
            registrar_compra(query.from_user.id, "gg", g["id"], PRECO_GGG_MIX)
            linhas.append(
                f"`{g['numero']}|{g['validade']}|{g.get('cvv','')}|{g.get('banco','')}|{g.get('bandeira','')}`"
            )
        if not linhas:
            update_saldo(query.from_user.id, total)
            await query.answer("❌ Itens indisponíveis no momento. Nenhum valor foi cobrado.", show_alert=True)
            return

        texto = f"✅ *Compra Mix GG — {qtd} unidades*\nTotal: R$ {total:.2f}\n\n" + "\n".join(linhas)
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("« Menu", callback_data="menu_principal")
        ]]), parse_mode="Markdown")
        return

    if data.startswith("ggs_comprar_"):
        ggg_id = int(data.split("_")[-1])
        ggg = get_ggg(ggg_id)
        if not ggg or ggg["vendido"]:
            await query.answer("❌ Este cartão já foi vendido!", show_alert=True)
            return

        user = get_user(query.from_user.id)
        if not user or user["saldo"] < PRECO_GGG_UNITARIA:
            await query.answer(f"❌ Saldo insuficiente! Saldo atual: R$ {user['saldo']:.2f}", show_alert=True)
            return

        if not debitar_saldo_se_suficiente(query.from_user.id, PRECO_GGG_UNITARIA):
            await query.answer("❌ Saldo insuficiente ou compra concorrente.", show_alert=True)
            return
        if not marcar_ggg_vendido_se_disponivel(ggg_id, query.from_user.id):
            update_saldo(query.from_user.id, PRECO_GGG_UNITARIA)
            await query.answer("❌ Este cartão acabou de ser vendido para outra pessoa.", show_alert=True)
            return
        registrar_compra(query.from_user.id, "gg", ggg_id, PRECO_GGG_UNITARIA)

        texto = (
            f"✅ *GG Comprado com Sucesso!*\n\n"
            f"💳 `{ggg['numero']}|{ggg['validade']}|{ggg.get('cvv','')}|"
            f"{ggg.get('banco','')}|{ggg.get('bandeira','')}`\n\n"
            f"💰 Debitado: R$ {PRECO_GGG_UNITARIA:.2f}"
        )
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("« Menu", callback_data="menu_principal")
        ]]), parse_mode="Markdown")
        return

    if data == "ggs_logins":
        from database.db import listar_logins, get_login, marcar_login_vendido
        logins = listar_logins()
        if not logins:
            await query.edit_message_text(
                "😔 Sem logins disponíveis.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Voltar", callback_data="comprar_menu")]]),
            )
            return

        buttons = []
        for l in logins[:10]:
            label = f"🔐 {l.get('tipo','Login')} — R${l.get('preco', 10):.0f}"
            buttons.append([InlineKeyboardButton(label, callback_data=f"ggs_login_comprar_{l['id']}")])
        buttons.append([InlineKeyboardButton("« Voltar", callback_data="comprar_menu")])
        await query.edit_message_text(
            f"🔐 *Logins Disponíveis* ({len(logins)})\nEscolha:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )
        return

    if data.startswith("ggs_login_comprar_"):
        from database.db import get_login
        login_id = int(data.split("_")[-1])
        login = get_login(login_id)
        if not login or login["vendido"]:
            await query.answer("❌ Login já vendido!", show_alert=True)
            return
        preco = login.get("preco", 10)
        user = get_user(query.from_user.id)
        if not user or user["saldo"] < preco:
            await query.answer("❌ Saldo insuficiente!", show_alert=True)
            return
        if not debitar_saldo_se_suficiente(query.from_user.id, preco):
            await query.answer("❌ Saldo insuficiente ou compra concorrente.", show_alert=True)
            return
        if not marcar_login_vendido_se_disponivel(login_id, query.from_user.id):
            update_saldo(query.from_user.id, preco)
            await query.answer("❌ Login acabou de ser vendido para outra pessoa.", show_alert=True)
            return
        registrar_compra(query.from_user.id, "login", login_id, preco)
        texto = (
            f"✅ *Login Comprado!*\n\n"
            f"📧 `{login.get('credencial','')}`\n"
            f"💰 Debitado: R$ {preco:.2f}"
        )
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("« Menu", callback_data="menu_principal")
        ]]), parse_mode="Markdown")
        return


async def ggs_busca_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    partes = texto.split(None, 1)
    if len(partes) < 2:
        return

    comando = partes[0].lower()
    valor = partes[1].strip()

    if comando == "buscar_banco":
        filtro = {"banco": valor}
        campo = "banco"
    elif comando == "buscar_bin":
        filtro = {"bin": valor}
        campo = "BIN"
    elif comando == "buscar_bandeira":
        filtro = {"bandeira": valor}
        campo = "bandeira"
    else:
        return

    resultados = listar_gggs(filtro)
    if not resultados:
        await update.message.reply_text(
            f"😔 Nenhum GG encontrado para {campo}: *{valor}*",
            parse_mode="Markdown"
        )
        return

    buttons = []
    for g in resultados[:15]:
        label = (
            f"{g.get('bandeira','?')} | {g.get('banco','?')} | "
            f"{g.get('bin','?')} — R${PRECO_GGG_UNITARIA:.0f}"
        )
        buttons.append([InlineKeyboardButton(label, callback_data=f"ggs_comprar_{g['id']}")])
    buttons.append([InlineKeyboardButton("« Voltar", callback_data="ggs_menu")])

    await update.message.reply_text(
        f"🔍 *GGs encontrados para {campo}: {valor}*\n{len(resultados)} resultado(s):",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )
