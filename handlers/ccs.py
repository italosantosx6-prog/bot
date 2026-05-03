"""
handlers/ccs.py
Menu de CCs com Unitária, Mix, Buscar banco/bin/bandeira.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import (
    listar_ccs,
    get_cc,
    marcar_cc_vendida_se_disponivel,
    get_user,
    update_saldo,
    registrar_compra,
    debitar_saldo_se_suficiente,
)
from config import PRECO_CC_UNITARIA, PRECO_CC_MIX, BOT_USERNAME

MENU_CC = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🔴 Unitária", callback_data="cc_unitaria"),
        InlineKeyboardButton("💸 Mix", callback_data="cc_mix"),
    ],
    [
        InlineKeyboardButton("🏦 Buscar banco »", switch_inline_query_current_chat="cc_buscar_banco "),
        InlineKeyboardButton("🔑 Buscar bin »", switch_inline_query_current_chat="cc_buscar_bin "),
    ],
    [InlineKeyboardButton("🏳 Buscar bandeira »", switch_inline_query_current_chat="cc_buscar_bandeira ")],
    [InlineKeyboardButton("« Voltar", callback_data="comprar_menu")],
])


async def ccs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💳 *CCs*\nEscolha uma opção:", reply_markup=MENU_CC, parse_mode="Markdown")


async def ccs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cc_menu":
        await query.edit_message_text("💳 *CCs*\nEscolha uma opção:", reply_markup=MENU_CC, parse_mode="Markdown")
        return

    if data == "cc_unitaria":
        ccs = listar_ccs()
        if not ccs:
            await query.edit_message_text(
                "😔 Sem CCs disponíveis no momento.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Voltar", callback_data="cc_menu")]]),
            )
            return

        buttons = []
        for c in ccs[:10]:
            label = f"{c.get('bandeira','?')} | {c.get('banco','?')} | {c.get('bin','?')} — R${PRECO_CC_UNITARIA:.0f}"
            buttons.append([InlineKeyboardButton(label, callback_data=f"cc_comprar_{c['id']}")])
        buttons.append([InlineKeyboardButton("« Voltar", callback_data="cc_menu")])

        await query.edit_message_text(
            f"💳 *CCs Disponíveis* ({len(ccs)} total)\nEscolha um cartão:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )
        return

    if data == "cc_mix":
        ccs = listar_ccs()
        total = len(ccs)
        buttons = [
            [InlineKeyboardButton("5 unid.", callback_data="cc_mix_5"),
             InlineKeyboardButton("10 unid.", callback_data="cc_mix_10")],
            [InlineKeyboardButton("20 unid.", callback_data="cc_mix_20"),
             InlineKeyboardButton("50 unid.", callback_data="cc_mix_50")],
            [InlineKeyboardButton("« Voltar", callback_data="cc_menu")],
        ]
        await query.edit_message_text(
            f"💸 *Pacote Mix de CCs*\n\n📦 {total} disponíveis\n💰 R$ {PRECO_CC_MIX:.0f}/unid.",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )
        return

    if data.startswith("cc_mix_"):
        qtd = int(data.split("_")[-1])
        total = round(qtd * PRECO_CC_MIX, 2)
        user = get_user(query.from_user.id)
        if not user or user["saldo"] < total:
            await query.answer(f"❌ Saldo insuficiente! Necessário: R$ {total:.2f}", show_alert=True)
            return

        ccs = listar_ccs()[:qtd]
        if len(ccs) < qtd:
            await query.answer(f"❌ Apenas {len(ccs)} disponíveis.", show_alert=True)
            return

        if not debitar_saldo_se_suficiente(query.from_user.id, total):
            await query.answer("❌ Saldo insuficiente ou compra concorrente. Tente novamente.", show_alert=True)
            return
        linhas = []
        for c in ccs:
            if not marcar_cc_vendida_se_disponivel(c["id"], query.from_user.id):
                continue
            registrar_compra(query.from_user.id, "cc", c["id"], PRECO_CC_MIX)
            linhas.append(f"`{c['numero']}|{c['validade']}|{c.get('cvv','')}|{c.get('banco','')}|{c.get('bandeira','')}`")
        if not linhas:
            update_saldo(query.from_user.id, total)
            await query.answer("❌ Itens indisponíveis no momento. Nenhum valor foi cobrado.", show_alert=True)
            return

        texto = f"✅ *Compra Mix CC — {qtd} unidades*\nTotal: R$ {total:.2f}\n\n" + "\n".join(linhas)
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("« Menu", callback_data="menu_principal")
        ]]), parse_mode="Markdown")
        return

    if data.startswith("cc_comprar_"):
        cc_id = int(data.split("_")[-1])
        cc = get_cc(cc_id)
        if not cc or cc["vendido"]:
            await query.answer("❌ Este cartão já foi vendido!", show_alert=True)
            return
        user = get_user(query.from_user.id)
        if not user or user["saldo"] < PRECO_CC_UNITARIA:
            await query.answer(f"❌ Saldo insuficiente!", show_alert=True)
            return
        if not debitar_saldo_se_suficiente(query.from_user.id, PRECO_CC_UNITARIA):
            await query.answer("❌ Saldo insuficiente ou compra concorrente.", show_alert=True)
            return
        if not marcar_cc_vendida_se_disponivel(cc_id, query.from_user.id):
            update_saldo(query.from_user.id, PRECO_CC_UNITARIA)
            await query.answer("❌ Este cartão acabou de ser vendido para outra pessoa.", show_alert=True)
            return
        registrar_compra(query.from_user.id, "cc", cc_id, PRECO_CC_UNITARIA)
        texto = (
            f"✅ *CC Comprada com Sucesso!*\n\n"
            f"💳 `{cc['numero']}|{cc['validade']}|{cc.get('cvv','')}|"
            f"{cc.get('banco','')}|{cc.get('bandeira','')}`\n\n"
            f"💰 Debitado: R$ {PRECO_CC_UNITARIA:.2f}"
        )
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("« Menu", callback_data="menu_principal")
        ]]), parse_mode="Markdown")
        return

    if data == "cc_buscar_banco":
        await query.edit_message_text(
            "🏦 *Buscar CC por Banco*\n\n"
            "👇 Toque no botão — o campo já abre com `cc_buscar_banco `!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Buscar banco (CC) »",
                    switch_inline_query_current_chat="cc_buscar_banco ")],
                [InlineKeyboardButton("« Voltar", callback_data="cc_menu")],
            ]),
            parse_mode="Markdown"
        )
        return

    if data == "cc_buscar_bin":
        await query.edit_message_text(
            "🔑 *Buscar CC por BIN*\n\n"
            "👇 Toque no botão — o campo já abre com `cc_buscar_bin `!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Buscar BIN (CC) »",
                    switch_inline_query_current_chat="cc_buscar_bin ")],
                [InlineKeyboardButton("« Voltar", callback_data="cc_menu")],
            ]),
            parse_mode="Markdown"
        )
        return

    if data == "cc_buscar_bandeira":
        await query.edit_message_text(
            "🏳 *Buscar CC por Bandeira*\n\n"
            "👇 Toque no botão — o campo já abre com `cc_buscar_bandeira `!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Buscar bandeira (CC) »",
                    switch_inline_query_current_chat="cc_buscar_bandeira ")],
                [InlineKeyboardButton("« Voltar", callback_data="cc_menu")],
            ]),
            parse_mode="Markdown"
        )
        return


async def ccs_busca_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    partes = texto.split(None, 1)
    if len(partes) < 2:
        return

    comando = partes[0].lower()
    valor = partes[1].strip()

    if comando == "cc_buscar_banco":
        filtro = {"banco": valor}
        campo = "banco"
    elif comando == "cc_buscar_bin":
        filtro = {"bin": valor}
        campo = "BIN"
    elif comando == "cc_buscar_bandeira":
        filtro = {"bandeira": valor}
        campo = "bandeira"
    else:
        return

    resultados = listar_ccs(filtro)
    if not resultados:
        await update.message.reply_text(
            f"😔 Nenhuma CC encontrada para {campo}: *{valor}*",
            parse_mode="Markdown"
        )
        return

    buttons = []
    for c in resultados[:15]:
        label = f"{c.get('bandeira','?')} | {c.get('banco','?')} | {c.get('bin','?')} — R${PRECO_CC_UNITARIA:.0f}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"cc_comprar_{c['id']}")])
    buttons.append([InlineKeyboardButton("« Voltar", callback_data="cc_menu")])

    await update.message.reply_text(
        f"🔍 *CCs encontradas para {campo}: {valor}*\n{len(resultados)} resultado(s):",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )
