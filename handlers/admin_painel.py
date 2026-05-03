"""
handlers/admin_painel.py

Painel Admin completo no Telegram.

Hierarquia:
  👑 DONO (OWNER_ID no config)  — acesso total, único que dá/remove cargos
  🔴 ADMIN                       — add produtos, stats, usuarios, broadcast, PIX
  🟡 MODERADOR                   — ver stats, ver perfis, banir
  🟢 REVENDEDOR                  — add produtos apenas

Comandos:
  /adm  — abre o painel (qualquer staff)
"""
from __future__ import annotations

import asyncio
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot, ForceReply
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from config import OWNER_ID, PRECO_GGG_UNITARIA, PRECO_CC_UNITARIA, STORE_NAME
from handlers.start import build_main_menu_markup, main_menu_caption
from utils.permissions import Cargo, get_cargo_db, pode, cargo_nome, requer_cargo, requer_dono
from database.db import (
    # staff
    listar_staff, adicionar_staff, remover_staff, get_staff_member,
    # users
    get_user, banir_usuario, desbanir_usuario, listar_usuarios, update_saldo, is_banido,
    # produtos
    adicionar_ggg, adicionar_cc, adicionar_login,
    listar_gggs, listar_ccs, listar_logins,
    remover_ggg, remover_cc, remover_login, limpar_estoque,
    # gifts
    criar_gift_code, listar_gift_codes,
    # pagamentos
    listar_pagamentos_pendentes, cancelar_pagamento_db, atualizar_pagamento, aprovar_pagamento_se_pendente,
    # stats
    stats_gerais,
)


# ══════════════════════════════════════════════════════════════════════════════
#  MENUS
# ══════════════════════════════════════════════════════════════════════════════

def menu_principal_adm(cargo: Cargo) -> InlineKeyboardMarkup:
    """Monta o menu conforme o cargo do operador."""
    rows = []

    # Sempre disponível para qualquer staff
    if pode(cargo, "add_produtos"):
        rows.append([
            InlineKeyboardButton("➕ Add GGG",   callback_data="adm_add_ggg"),
            InlineKeyboardButton("➕ Add CC",    callback_data="adm_add_cc"),
        ])
        rows.append([
            InlineKeyboardButton("➕ Add Login", callback_data="adm_add_login"),
            InlineKeyboardButton("🗑 Limpar estoque", callback_data="adm_limpar_menu"),
        ])

    if pode(cargo, "ver_stats"):
        rows.append([InlineKeyboardButton("📊 Estatísticas", callback_data="adm_stats")])

    if pode(cargo, "ver_perfil_usuario"):
        rows.append([
            InlineKeyboardButton("👤 Gerenciar Usuário", callback_data="adm_user_busca"),
            InlineKeyboardButton("📋 Listar Usuários",   callback_data="adm_user_lista_0"),
        ])

    if pode(cargo, "broadcast"):
        rows.append([InlineKeyboardButton("📢 Broadcast",   callback_data="adm_broadcast")])

    if pode(cargo, "ver_pagamentos"):
        rows.append([InlineKeyboardButton("💳 PIX Pendentes", callback_data="adm_pix_lista")])

    if pode(cargo, "gerenciar_gift"):
        rows.append([InlineKeyboardButton("🎁 Gerenciar Gifts", callback_data="adm_gift_menu")])

    if pode(cargo, "ver_admins"):
        rows.append([
            InlineKeyboardButton("👑 Gerenciar Staff", callback_data="adm_staff_lista"),
            InlineKeyboardButton("➕ Dar Cargo",       callback_data="adm_staff_dar"),
        ])

    rows.append([InlineKeyboardButton("❌ Fechar", callback_data="adm_fechar")])
    return InlineKeyboardMarkup(rows)


BTN_VOLTAR_ADM = InlineKeyboardButton("« Painel", callback_data="adm_menu")


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT  /adm
# ══════════════════════════════════════════════════════════════════════════════

async def adm_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cargo = get_cargo_db(uid)
    if cargo is None:
        await update.message.reply_text("🚫 *Acesso negado.*", parse_mode="Markdown")
        return

    context.user_data["_cargo"] = cargo
    context.user_data["_adm_modo"] = None   # limpa estado

    await update.message.reply_text(
        _texto_boas_vindas(update.effective_user, cargo),
        reply_markup=menu_principal_adm(cargo),
        parse_mode="Markdown"
    )


def _texto_boas_vindas(user, cargo: Cargo) -> str:
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    return (
        f"🛠️ *Painel Administrativo*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Operador: @{user.username or user.first_name}\n"
        f"🏷 Cargo: {cargo_nome(cargo)}\n"
        f"🕐 Acesso: {agora}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Escolha uma ação:"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  CALLBACK ROUTER
# ══════════════════════════════════════════════════════════════════════════════

async def adm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _limpar_prompts_admin(context, query.message.chat_id)

    uid  = query.from_user.id
    cargo = get_cargo_db(uid)
    if cargo is None:
        await query.answer("🚫 Sem permissão.", show_alert=True)
        return

    context.user_data["_cargo"] = cargo
    data = query.data

    # ── Menu principal ────────────────────────────────────────────────────────
    if data == "adm_menu":
        await query.edit_message_text(
            _texto_boas_vindas(query.from_user, cargo),
            reply_markup=menu_principal_adm(cargo),
            parse_mode="Markdown"
        )
        return

    if data == "adm_fechar":
        await query.delete_message()
        return

    # ── Estatísticas ──────────────────────────────────────────────────────────
    if data == "adm_stats":
        if not pode(cargo, "ver_stats"):
            await query.answer("🚫 Sem permissão.", show_alert=True)
            return
        s = stats_gerais()
        txt = (
            f"📊 *Estatísticas Gerais*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 Usuários cadastrados: `{s['total_users']}`\n\n"
            f"🔑 *GGGs*\n"
            f"├ Total: `{s['total_gggs']}`\n"
            f"├ Vendidos: `{s['gggs_vendidos']}`\n"
            f"└ Estoque: `{s['gggs_stock']}`\n\n"
            f"💳 *CCs*\n"
            f"├ Total: `{s['total_ccs']}`\n"
            f"├ Vendidas: `{s['ccs_vendidas']}`\n"
            f"└ Estoque: `{s['ccs_stock']}`\n\n"
            f"🔐 *Logins*\n"
            f"├ Total: `{s['total_logins']}`\n"
            f"├ Vendidos: `{s['logins_vend']}`\n"
            f"└ Estoque: `{s['logins_stock']}`\n\n"
            f"💰 *Financeiro*\n"
            f"├ Faturamento total: `R$ {s['faturamento']:.2f}`\n"
            f"└ Saldo em carteiras: `R$ {s['saldo_total']:.2f}`"
        )
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]]), parse_mode="Markdown")
        return

    # ── Add GGG ───────────────────────────────────────────────────────────────
    if data == "adm_add_ggg":
        if not pode(cargo, "add_produtos"):
            await query.answer("🚫 Sem permissão.", show_alert=True); return
        context.user_data["_adm_modo"] = "add_ggg"
        await query.edit_message_text(
            "➕ *Adicionar GGGs*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "Envie um ou vários cartões (um por linha):\n\n"
            "`NUMERO|VALIDADE|CVV|BANCO|BANDEIRA|BIN`\n\n"
            "📌 Exemplo:\n"
            "`4984081234567890|08/2028|123|BANCO DO BRASIL|VISA|498408`\n\n"
            "⚡ Pode colar vários de uma vez!",
            reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]]),
            parse_mode="Markdown"
        )
        await _abrir_campo_digitacao_admin(
            context=context,
            chat_id=query.message.chat_id,
            placeholder="Cole os GGGs aqui",
            texto="✍️ Envie agora os GGGs (texto ou arquivo .txt/.csv)."
        )
        return

    # ── Add CC ────────────────────────────────────────────────────────────────
    if data == "adm_add_cc":
        if not pode(cargo, "add_produtos"):
            await query.answer("🚫 Sem permissão.", show_alert=True); return
        context.user_data["_adm_modo"] = "add_cc"
        await query.edit_message_text(
            "➕ *Adicionar CCs*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "`NUMERO|VALIDADE|CVV|BANCO|BANDEIRA|BIN`\n\n"
            "📌 Exemplo:\n"
            "`5464521234567890|09/2028|456|ITAU|MASTERCARD|546452`",
            reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]]),
            parse_mode="Markdown"
        )
        await _abrir_campo_digitacao_admin(
            context=context,
            chat_id=query.message.chat_id,
            placeholder="Cole as CCs aqui",
            texto="✍️ Envie agora as CCs (texto ou arquivo .txt/.csv)."
        )
        return

    # ── Add Login ─────────────────────────────────────────────────────────────
    if data == "adm_add_login":
        if not pode(cargo, "add_produtos"):
            await query.answer("🚫 Sem permissão.", show_alert=True); return
        context.user_data["_adm_modo"] = "add_login"
        await query.edit_message_text(
            "➕ *Adicionar Logins*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "`TIPO|EMAIL:SENHA|PRECO`\n\n"
            "📌 Exemplo:\n"
            "`Netflix|conta@email.com:senha123|15`",
            reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]]),
            parse_mode="Markdown"
        )
        await _abrir_campo_digitacao_admin(
            context=context,
            chat_id=query.message.chat_id,
            placeholder="Cole os logins aqui",
            texto="✍️ Envie agora os logins (texto ou arquivo .txt/.csv)."
        )
        return

    # ── Limpar estoque ────────────────────────────────────────────────────────
    if data == "adm_limpar_menu":
        if not pode(cargo, "remover_produto") and cargo != Cargo.DONO:
            await query.answer("🚫 Apenas Dono/Admin.", show_alert=True); return
        await query.edit_message_text(
            "🗑 *Limpar Estoque*\n━━━━━━━━━━━━━━━━━━━━━\n⚠️ Isso remove TODOS os itens NÃO vendidos da categoria!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 GGGs não vendidos",    callback_data="adm_limpar_gggs")],
                [InlineKeyboardButton("🗑 CCs não vendidas",     callback_data="adm_limpar_ccs")],
                [InlineKeyboardButton("🗑 Logins não vendidos",  callback_data="adm_limpar_logins")],
                [BTN_VOLTAR_ADM],
            ]),
            parse_mode="Markdown"
        )
        return

    if data in ("adm_limpar_gggs", "adm_limpar_ccs", "adm_limpar_logins"):
        if not pode(cargo, "remover_produto") and cargo != Cargo.DONO:
            await query.answer("🚫 Sem permissão.", show_alert=True); return
        tabela = {"adm_limpar_gggs": "gggs", "adm_limpar_ccs": "ccs", "adm_limpar_logins": "logins"}[data]
        limpar_estoque(tabela)
        await query.edit_message_text(
            f"✅ Estoque de *{tabela.upper()}* limpo!",
            reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]]),
            parse_mode="Markdown"
        )
        return

    # ── Gerenciar usuário por ID ───────────────────────────────────────────────
    if data == "adm_user_busca":
        if not pode(cargo, "ver_perfil_usuario"):
            await query.answer("🚫 Sem permissão.", show_alert=True); return
        context.user_data["_adm_modo"] = "busca_user"
        await query.edit_message_text(
            "🔍 *Buscar Usuário*\n━━━━━━━━━━━━━━━━━━━━━\n"
            "Envie o *Telegram ID* do usuário:",
            reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]]),
            parse_mode="Markdown"
        )
        await _abrir_campo_digitacao_admin(
            context=context,
            chat_id=query.message.chat_id,
            placeholder="Digite o ID do usuário",
            texto="✍️ Envie agora o ID numérico do usuário."
        )
        return

    if data.startswith("adm_user_ver_"):
        uid_alvo = int(data.split("_")[-1])
        await _mostrar_perfil_usuario(query, context, uid_alvo, cargo)
        return

    if data.startswith("adm_banir_"):
        if not pode(cargo, "banir_usuario"):
            await query.answer("🚫 Sem permissão.", show_alert=True); return
        uid_alvo = int(data.split("_")[-1])
        banir_usuario(uid_alvo, uid)
        await query.edit_message_text(
            f"🚫 Usuário `{uid_alvo}` foi *banido*.",
            reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]]),
            parse_mode="Markdown"
        )
        try:
            await context.bot.send_message(uid_alvo, "🚫 Sua conta foi suspensa. Entre em contato com o suporte.")
        except Exception:
            pass
        return

    if data.startswith("adm_desbanir_"):
        if not pode(cargo, "banir_usuario"):
            await query.answer("🚫 Sem permissão.", show_alert=True); return
        uid_alvo = int(data.split("_")[-1])
        desbanir_usuario(uid_alvo)
        await query.edit_message_text(
            f"✅ Usuário `{uid_alvo}` foi *desbanido*.",
            reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]]),
            parse_mode="Markdown"
        )
        try:
            await context.bot.send_message(uid_alvo, "✅ Sua conta foi reativada!")
        except Exception:
            pass
        return

    if data.startswith("adm_darsaldo_"):
        if not pode(cargo, "dar_saldo"):
            await query.answer("🚫 Sem permissão.", show_alert=True); return
        uid_alvo = int(data.split("_")[-1])
        context.user_data["_adm_modo"] = f"dar_saldo_{uid_alvo}"
        await query.edit_message_text(
            f"💰 *Dar Saldo*\n━━━━━━━━━━━━━━━━━━━━━\n"
            f"Usuário: `{uid_alvo}`\n\n"
            f"Digite o valor a adicionar (ou negativo para remover):\n"
            f"Ex: `50` ou `-10`",
            reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]]),
            parse_mode="Markdown"
        )
        await _abrir_campo_digitacao_admin(
            context=context,
            chat_id=query.message.chat_id,
            placeholder="Digite o valor do ajuste",
            texto="✍️ Envie agora o valor (ex: 50 ou -10)."
        )
        return

    # ── Lista de usuários paginada ─────────────────────────────────────────────
    if data.startswith("adm_user_lista_"):
        if not pode(cargo, "ver_perfil_usuario"):
            await query.answer("🚫 Sem permissão.", show_alert=True); return
        offset = int(data.split("_")[-1])
        users = listar_usuarios(limit=8, offset=offset)
        if not users:
            await query.answer("Sem mais usuários.", show_alert=True); return

        txt = f"👥 *Usuários* (pág. {offset//8 + 1})\n━━━━━━━━━━━━━━━━━━━━━\n"
        buttons = []
        for u in users:
            ban_icon = "🚫" if u.get("banido") else "✅"
            label = f"{ban_icon} {u.get('username') or u['telegram_id']} — R$ {u['saldo']:.2f}"
            buttons.append([InlineKeyboardButton(label, callback_data=f"adm_user_ver_{u['telegram_id']}")])

        nav = []
        if offset > 0:
            nav.append(InlineKeyboardButton("⬅️", callback_data=f"adm_user_lista_{offset-8}"))
        if len(users) == 8:
            nav.append(InlineKeyboardButton("➡️", callback_data=f"adm_user_lista_{offset+8}"))
        if nav:
            buttons.append(nav)
        buttons.append([BTN_VOLTAR_ADM])

        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
        return

    # ── Broadcast ────────────────────────────────────────────────────────────
    if data == "adm_broadcast":
        if not pode(cargo, "broadcast"):
            await query.answer("🚫 Sem permissão.", show_alert=True); return
        context.user_data["_adm_modo"] = "broadcast"
        await query.edit_message_text(
            "📢 *Broadcast*\n━━━━━━━━━━━━━━━━━━━━━\n"
            "Envie a mensagem que será disparada para *TODOS* os usuários.\n\n"
            "⚠️ Suporta Markdown. Confirme antes de enviar.",
            reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]]),
            parse_mode="Markdown"
        )
        await _abrir_campo_digitacao_admin(
            context=context,
            chat_id=query.message.chat_id,
            placeholder="Digite a mensagem do broadcast",
            texto="✍️ Envie agora a mensagem que será disparada."
        )
        return

    if data.startswith("adm_broadcast_confirm_"):
        if not pode(cargo, "broadcast"):
            await query.answer("🚫 Sem permissão.", show_alert=True); return
        msg_id = data.replace("adm_broadcast_confirm_", "")
        msg_texto = context.user_data.get(f"broadcast_msg_{msg_id}", "")
        if not msg_texto:
            await query.answer("Mensagem não encontrada.", show_alert=True); return

        await query.edit_message_text("📢 *Enviando broadcast...*", parse_mode="Markdown")
        asyncio.create_task(_executar_broadcast(context.bot, msg_texto, query.message))
        return

    # ── PIX pendentes ────────────────────────────────────────────────────────
    if data == "adm_pix_lista":
        if not pode(cargo, "ver_pagamentos"):
            await query.answer("🚫 Sem permissão.", show_alert=True); return
        pix = listar_pagamentos_pendentes()
        if not pix:
            await query.edit_message_text(
                "✅ Nenhum PIX pendente.",
                reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]])
            ); return

        buttons = []
        for p in pix[:10]:
            label = f"R$ {p['valor']:.2f} — ID {p['payment_id'][:8]}... — {p['telegram_id']}"
            buttons.append([InlineKeyboardButton(label, callback_data=f"adm_pix_ver_{p['payment_id']}")])
        buttons.append([BTN_VOLTAR_ADM])

        await query.edit_message_text(
            f"💳 *PIX Pendentes* ({len(pix)})",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )
        return

    if data.startswith("adm_pix_ver_"):
        if not pode(cargo, "ver_pagamentos"):
            await query.answer("🚫 Sem permissão.", show_alert=True); return
        pid = data.replace("adm_pix_ver_", "")
        from database.db import get_pagamento
        pag = get_pagamento(pid)
        if not pag:
            await query.answer("Pagamento não encontrado.", show_alert=True); return
        txt = (
            f"💳 *Detalhes do PIX*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 Payment ID: `{pid}`\n"
            f"👤 Usuário: `{pag['telegram_id']}`\n"
            f"💰 Valor: R$ {pag['valor']:.2f}\n"
            f"📅 Criado: {str(pag.get('created_at',''))[:16]}\n"
            f"📌 Status: `{pag['status']}`"
        )
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Aprovar Manual", callback_data=f"adm_pix_aprovar_{pid}")],
            [InlineKeyboardButton("❌ Cancelar",       callback_data=f"adm_pix_cancelar_{pid}")],
            [InlineKeyboardButton("« Voltar",          callback_data="adm_pix_lista")],
        ]), parse_mode="Markdown")
        return

    if data.startswith("adm_pix_cancelar_"):
        if not pode(cargo, "cancelar_pagamento"):
            await query.answer("🚫 Sem permissão.", show_alert=True); return
        pid = data.replace("adm_pix_cancelar_", "")
        cancelar_pagamento_db(pid)
        await query.edit_message_text("❌ PIX cancelado.", reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]]))
        return

    if data.startswith("adm_pix_aprovar_"):
        if not pode(cargo, "cancelar_pagamento"):
            await query.answer("🚫 Sem permissão.", show_alert=True); return
        pid = data.replace("adm_pix_aprovar_", "")
        from database.db import get_pagamento, pagar_comissao
        pag = get_pagamento(pid)
        if pag and aprovar_pagamento_se_pendente(pid):
            tid = int(pag["telegram_id"])
            update_saldo(tid, pag["valor"])
            pagar_comissao(tid, pag["valor"])
            try:
                user = get_user(tid)
                saldo_txt = ""
                if user:
                    saldo_txt = f"\n💼 Saldo atual: *R$ {float(user['saldo']):.2f}*"
                await context.bot.send_message(
                    tid,
                    f"✅ *Pagamento confirmado!*\n\n"
                    f"💰 Valor creditado: *R$ {float(pag['valor']):.2f}*{saldo_txt}\n\n"
                    f"{main_menu_caption()}",
                    reply_markup=build_main_menu_markup(tid),
                    parse_mode="Markdown",
                )
            except Exception:
                pass
        await query.edit_message_text("✅ PIX aprovado e saldo creditado.", reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]]))
        return

    # ── Gifts ─────────────────────────────────────────────────────────────────
    if data == "adm_gift_menu":
        if not pode(cargo, "gerenciar_gift"):
            await query.answer("🚫 Sem permissão.", show_alert=True); return
        await query.edit_message_text(
            "🎁 *Gerenciar Gifts*\n━━━━━━━━━━━━━━━━━━━━━\n"
            "Escolha uma opção:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Gerar Gift(s)", callback_data="adm_gift_gerar")],
                [InlineKeyboardButton("📋 Listar últimos", callback_data="adm_gift_lista")],
                [BTN_VOLTAR_ADM],
            ]),
            parse_mode="Markdown"
        )
        return

    if data == "adm_gift_gerar":
        if not pode(cargo, "gerenciar_gift"):
            await query.answer("🚫 Sem permissão.", show_alert=True); return
        context.user_data["_adm_modo"] = "gift_gerar"
        await query.edit_message_text(
            "➕ *Gerar Gift(s)*\n━━━━━━━━━━━━━━━━━━━━━\n"
            "Envie no formato:\n"
            "`VALOR|QUANTIDADE|DIAS_VALIDADE|ID_ALVO(opcional)`\n\n"
            "Exemplo para uso geral:\n"
            "`25|3|7`\n\n"
            "Exemplo para usuário específico:\n"
            "`10|1|3|123456789`",
            reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]]),
            parse_mode="Markdown",
        )
        await _abrir_campo_digitacao_admin(
            context=context,
            chat_id=query.message.chat_id,
            placeholder="VALOR|QTD|DIAS|ID(opcional)",
            texto="✍️ Envie agora no formato: VALOR|QUANTIDADE|DIAS|ID(opcional)."
        )
        return

    if data == "adm_gift_lista":
        if not pode(cargo, "gerenciar_gift"):
            await query.answer("🚫 Sem permissão.", show_alert=True); return
        gifts = listar_gift_codes(limit=20)
        if not gifts:
            await query.edit_message_text(
                "📭 Nenhum gift encontrado.",
                reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]])
            )
            return
        linhas = ["🎁 *Últimos Gifts*"]
        for g in gifts:
            status = "✅ Usado" if g.get("used") else "🟢 Ativo"
            alvo = "geral" if int(g.get("telegram_id") or 0) == 0 else str(g.get("telegram_id"))
            linhas.append(f"`{g.get('code')}` • R$ {float(g.get('valor') or 0):.2f} • {status} • alvo `{alvo}`")
        await query.edit_message_text(
            "\n".join(linhas),
            reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]]),
            parse_mode="Markdown"
        )
        return

    # ── Staff ─────────────────────────────────────────────────────────────────
    if data == "adm_staff_lista":
        if not pode(cargo, "ver_admins"):
            await query.answer("🚫 Sem permissão.", show_alert=True); return
        staff = listar_staff()
        linhas = [f"👑 *Lista de Staff*\n━━━━━━━━━━━━━━━━━━━━━"]
        for s in staff:
            c = Cargo(s["cargo"])
            linhas.append(f"{cargo_nome(c)} — @{s.get('username') or s['telegram_id']} (`{s['telegram_id']}`)")
        if not staff:
            linhas.append("Nenhum staff cadastrado.")

        buttons = []
        for s in staff:
            buttons.append([InlineKeyboardButton(
                f"🗑 Remover @{s.get('username') or s['telegram_id']}",
                callback_data=f"adm_staff_remover_{s['telegram_id']}"
            )])
        buttons.append([BTN_VOLTAR_ADM])

        await query.edit_message_text(
            "\n".join(linhas),
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )
        return

    if data == "adm_staff_dar":
        if not pode(cargo, "dar_cargo"):
            await query.answer("🚫 Sem permissão.", show_alert=True); return
        context.user_data["_adm_modo"] = "dar_cargo"
        await query.edit_message_text(
            "➕ *Dar Cargo*\n━━━━━━━━━━━━━━━━━━━━━\n"
            "Envie neste formato:\n\n"
            "`ID_TELEGRAM|CARGO|@username`\n\n"
            "Cargos disponíveis:\n"
            "• `admin`\n"
            "• `moderador`\n"
            "• `revendedor`\n\n"
            "📌 Ex: `123456789|admin|@joao`",
            reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]]),
            parse_mode="Markdown"
        )
        await _abrir_campo_digitacao_admin(
            context=context,
            chat_id=query.message.chat_id,
            placeholder="ID|CARGO|@username",
            texto="✍️ Envie agora no formato: ID_TELEGRAM|CARGO|@username."
        )
        return

    if data.startswith("adm_staff_remover_"):
        if not pode(cargo, "remover_cargo"):
            await query.answer("🚫 Sem permissão.", show_alert=True); return
        uid_alvo = int(data.split("_")[-1])
        if uid_alvo == OWNER_ID:
            await query.answer("❌ Não pode remover o dono.", show_alert=True); return
        remover_staff(uid_alvo)
        await query.edit_message_text(
            f"✅ Staff `{uid_alvo}` removido.",
            reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]]),
            parse_mode="Markdown"
        )
        return


# ══════════════════════════════════════════════════════════════════════════════
#  HANDLER DE MENSAGENS DO ADMIN
# ══════════════════════════════════════════════════════════════════════════════

async def adm_msg_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    cargo = get_cargo_db(uid)
    if cargo is None:
        return

    modo = context.user_data.get("_adm_modo")
    if not modo:
        return

    await _limpar_prompts_admin(context, update.effective_chat.id)
    texto = await _extrair_texto_admin(update, context)
    if texto is None:
        return

    # ── Adicionar GGG ─────────────────────────────────────────────────────────
    if modo == "add_ggg":
        added, erros = _processar_cards(texto, "ggg")
        context.user_data["_adm_modo"] = None
        resp = f"✅ *{added} GGG(s) adicionado(s)!*"
        if erros:
            resp += f"\n\n❌ {len(erros)} erro(s):\n" + "\n".join(erros[:3])
        await update.message.reply_text(resp, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]]))
        return

    # ── Adicionar CC ──────────────────────────────────────────────────────────
    if modo == "add_cc":
        added, erros = _processar_cards(texto, "cc")
        context.user_data["_adm_modo"] = None
        resp = f"✅ *{added} CC(s) adicionada(s)!*"
        if erros:
            resp += f"\n\n❌ {len(erros)} erro(s):\n" + "\n".join(erros[:3])
        await update.message.reply_text(resp, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]]))
        return

    # ── Adicionar Login ───────────────────────────────────────────────────────
    if modo == "add_login":
        added, erros = _processar_logins(texto)
        context.user_data["_adm_modo"] = None
        resp = f"✅ *{added} Login(s) adicionado(s)!*"
        if erros:
            resp += f"\n\n❌ {len(erros)} erro(s):\n" + "\n".join(erros[:3])
        await update.message.reply_text(resp, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]]))
        return

    # ── Buscar usuário ────────────────────────────────────────────────────────
    if modo == "busca_user":
        if not texto.isdigit():
            await update.message.reply_text("❌ Envie apenas o ID numérico do usuário.")
            return
        uid_alvo = int(texto)
        context.user_data["_adm_modo"] = None
        await _mostrar_perfil_usuario_msg(update, context, uid_alvo, cargo)
        return

    # ── Dar saldo ─────────────────────────────────────────────────────────────
    if modo and modo.startswith("dar_saldo_"):
        uid_alvo = int(modo.split("_")[-1])
        try:
            valor = float(texto.replace(",", "."))
        except ValueError:
            await update.message.reply_text("❌ Valor inválido. Ex: `50` ou `-10`", parse_mode="Markdown")
            return
        update_saldo(uid_alvo, valor)
        context.user_data["_adm_modo"] = None
        user = get_user(uid_alvo)
        sinal = "+" if valor >= 0 else ""
        await update.message.reply_text(
            f"✅ *Saldo atualizado!*\n"
            f"👤 ID: `{uid_alvo}`\n"
            f"💰 Ajuste: `{sinal}R$ {valor:.2f}`\n"
            f"💼 Novo saldo: `R$ {user['saldo']:.2f}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]])
        )
        try:
            sinal_msg = "adicionado" if valor >= 0 else "removido"
            await context.bot.send_message(
                uid_alvo,
                f"💰 *Seu saldo foi atualizado!*\n{sinal}R$ {valor:.2f} {sinal_msg} pelo admin.\nSaldo atual: R$ {user['saldo']:.2f}",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return

    # ── Broadcast preview ────────────────────────────────────────────────────
    if modo == "broadcast":
        import time
        msg_id = str(int(time.time()))
        context.user_data[f"broadcast_msg_{msg_id}"] = texto
        context.user_data["_adm_modo"] = None
        await update.message.reply_text(
            f"📢 *Preview da mensagem:*\n━━━━━━━━━━━━━━━━━━━━━\n{texto}\n━━━━━━━━━━━━━━━━━━━━━\n"
            f"Confirma o envio para TODOS os usuários?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirmar e Enviar", callback_data=f"adm_broadcast_confirm_{msg_id}")],
                [InlineKeyboardButton("❌ Cancelar",           callback_data="adm_menu")],
            ]),
            parse_mode="Markdown"
        )
        return

    # ── Dar cargo ────────────────────────────────────────────────────────────
    if modo == "dar_cargo":
        if not pode(cargo, "dar_cargo"):
            return
        partes = [p.strip() for p in texto.split("|")]
        if len(partes) < 2:
            await update.message.reply_text("❌ Formato: `ID|CARGO|@username`", parse_mode="Markdown")
            return
        try:
            uid_alvo = int(partes[0])
        except ValueError:
            await update.message.reply_text("❌ ID inválido."); return

        cargo_str = partes[1].lower()
        username  = partes[2].lstrip("@") if len(partes) > 2 else ""

        mapa = {"admin": Cargo.ADMIN, "moderador": Cargo.MODERADOR, "revendedor": Cargo.REVENDEDOR}
        if cargo_str not in mapa:
            await update.message.reply_text("❌ Cargo inválido. Use: admin, moderador ou revendedor")
            return

        if uid_alvo == OWNER_ID:
            await update.message.reply_text("❌ O dono não precisa de cargo.")
            return

        novo_cargo = mapa[cargo_str]
        adicionar_staff(uid_alvo, username, int(novo_cargo), uid)
        context.user_data["_adm_modo"] = None

        await update.message.reply_text(
            f"✅ *Cargo atribuído!*\n"
            f"👤 ID: `{uid_alvo}`\n"
            f"🏷 Cargo: {cargo_nome(novo_cargo)}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]])
        )
        try:
            await context.bot.send_message(
                uid_alvo,
                f"🎉 Você recebeu o cargo *{cargo_nome(novo_cargo)}* na {STORE_NAME}!\nUse /adm para acessar o painel.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return

    # ── Gerar gift(s) ─────────────────────────────────────────────────────────
    if modo == "gift_gerar":
        if not pode(cargo, "gerenciar_gift"):
            return
        partes = [p.strip() for p in texto.split("|")]
        if len(partes) < 3:
            await update.message.reply_text("❌ Formato inválido. Use `VALOR|QUANTIDADE|DIAS|ID(opcional)`", parse_mode="Markdown")
            return
        try:
            valor = float(partes[0].replace(",", "."))
            quantidade = int(partes[1])
            dias = int(partes[2])
            alvo = int(partes[3]) if len(partes) > 3 and partes[3].isdigit() else 0
        except ValueError:
            await update.message.reply_text("❌ Valor, quantidade e dias devem ser numéricos.")
            return
        if valor <= 0 or quantidade <= 0 or quantidade > 50 or dias < 0 or dias > 365:
            await update.message.reply_text("❌ Valores fora do limite. Quantidade máx: 50, dias: 0..365.")
            return

        from datetime import timedelta
        import secrets
        expiracao = (datetime.utcnow() + timedelta(days=dias)).isoformat() if dias > 0 else None
        criados = []
        for _ in range(quantidade):
            code = f"INF{secrets.token_hex(4).upper()}"
            criar_gift_code(code=code, valor=valor, telegram_id=alvo, criado_por=uid, expires_at=expiracao)
            criados.append(code)

        context.user_data["_adm_modo"] = None
        await update.message.reply_text(
            "✅ *Gift(s) gerado(s)!*\n\n"
            f"💰 Valor: R$ {valor:.2f}\n"
            f"🔢 Quantidade: {quantidade}\n"
            f"🎯 Alvo: `{alvo or 0}`\n"
            f"⏳ Validade (dias): {dias}\n\n"
            "Códigos:\n" + "\n".join([f"`{c}`" for c in criados]),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]])
        )
        return

    await update.message.reply_text(
        "ℹ️ Ação não reconhecida. Use /adm e escolha novamente a opção desejada.",
        reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]])
    )


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _processar_cards(texto: str, tipo: str) -> tuple[int, list[str]]:
    linhas = [l.strip() for l in texto.split("\n") if l.strip()]
    added, erros = 0, []
    fn = adicionar_ggg if tipo == "ggg" else adicionar_cc
    preco = PRECO_GGG_UNITARIA if tipo == "ggg" else PRECO_CC_UNITARIA

    for linha in linhas:
        partes = [p.strip() for p in linha.split("|")]
        if len(partes) < 2:
            erros.append(f"Linha curta: {linha[:30]}")
            continue
        try:
            fn({
                "numero":   partes[0],
                "validade": partes[1],
                "cvv":      partes[2] if len(partes) > 2 else "",
                "banco":    partes[3] if len(partes) > 3 else "",
                "bandeira": partes[4] if len(partes) > 4 else "",
                "bin":      partes[5] if len(partes) > 5 else partes[0][:6],
                "vendido":  False,
                "preco":    preco,
            })
            added += 1
        except Exception as e:
            erros.append(f"Erro: {e} — {linha[:30]}")
    return added, erros


def _processar_logins(texto: str) -> tuple[int, list[str]]:
    linhas = [l.strip() for l in texto.split("\n") if l.strip()]
    added, erros = 0, []
    for linha in linhas:
        partes = [p.strip() for p in linha.split("|")]
        if len(partes) < 2:
            erros.append(f"Linha curta: {linha[:30]}")
            continue
        try:
            adicionar_login({
                "tipo":       partes[0],
                "credencial": partes[1],
                "preco":      float(partes[2]) if len(partes) > 2 else 10.0,
                "vendido":    False,
            })
            added += 1
        except Exception as e:
            erros.append(f"Erro: {e} — {linha[:30]}")
    return added, erros


async def _extrair_texto_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """
    Aceita texto normal ou arquivo .txt enviado no painel admin.
    """
    msg = update.message
    if msg is None:
        return None

    if msg.text and msg.text.strip():
        return msg.text.strip()

    if msg.document:
        nome = (msg.document.file_name or "").lower()
        mime = (msg.document.mime_type or "").lower()
        if not (nome.endswith(".txt") or nome.endswith(".csv") or mime.startswith("text/")):
            await msg.reply_text("❌ Envie texto na mensagem ou arquivo `.txt`/`.csv`.", parse_mode="Markdown")
            return None
        try:
            tg_file = await msg.document.get_file()
            blob = await tg_file.download_as_bytearray()
            texto = bytes(blob).decode("utf-8", errors="ignore").strip()
            if not texto:
                await msg.reply_text("❌ O arquivo está vazio.")
                return None
            return texto
        except Exception:
            await msg.reply_text("❌ Não consegui ler o arquivo. Tente enviar o conteúdo como texto.")
            return None

    await msg.reply_text("❌ Envie o conteúdo como texto ou arquivo `.txt`.")
    return None


async def _abrir_campo_digitacao_admin(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    placeholder: str,
    texto: str,
):
    """Abre o campo de digitação (ForceReply) para o próximo passo do painel admin."""
    try:
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=texto,
            reply_markup=ForceReply(selective=True, input_field_placeholder=placeholder),
        )
        ids = context.user_data.get("_adm_prompt_msg_ids", [])
        ids.append(msg.message_id)
        context.user_data["_adm_prompt_msg_ids"] = ids[-10:]
    except Exception:
        # Fallback silencioso: o fluxo continua funcionando mesmo sem ForceReply.
        pass


async def _limpar_prompts_admin(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """
    Remove prompts antigos de ForceReply para não poluir o chat do admin.
    """
    ids = context.user_data.get("_adm_prompt_msg_ids", [])
    if not ids:
        return
    for msg_id in ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass
    context.user_data["_adm_prompt_msg_ids"] = []


async def _mostrar_perfil_usuario(query, context, uid_alvo: int, cargo: Cargo):
    user = get_user(uid_alvo)
    if not user:
        await query.edit_message_text(
            "❌ Usuário não encontrado.",
            reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]])
        )
        return

    banido = user.get("banido", False)
    txt = (
        f"👤 *Perfil do Usuário*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: `{user['telegram_id']}`\n"
        f"📛 Username: @{user.get('username') or 'N/A'}\n"
        f"💰 Saldo: R$ {user['saldo']:.2f}\n"
        f"💸 Comissão: R$ {user['comissao']:.2f}\n"
        f"🔗 Referido por: `{user.get('referido_por') or 'Nenhum'}`\n"
        f"📅 Cadastro: {str(user.get('created_at',''))[:10]}\n"
        f"🚫 Banido: {'Sim' if banido else 'Não'}"
    )

    btns = []
    if pode(cargo, "dar_saldo"):
        btns.append([InlineKeyboardButton("💰 Dar/Remover Saldo", callback_data=f"adm_darsaldo_{uid_alvo}")])
    if pode(cargo, "banir_usuario"):
        if banido:
            btns.append([InlineKeyboardButton("✅ Desbanir", callback_data=f"adm_desbanir_{uid_alvo}")])
        else:
            btns.append([InlineKeyboardButton("🚫 Banir", callback_data=f"adm_banir_{uid_alvo}")])
    btns.append([BTN_VOLTAR_ADM])

    await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(btns), parse_mode="Markdown")


async def _mostrar_perfil_usuario_msg(update, context, uid_alvo: int, cargo: Cargo):
    user = get_user(uid_alvo)
    if not user:
        await update.message.reply_text("❌ Usuário não encontrado.",
            reply_markup=InlineKeyboardMarkup([[BTN_VOLTAR_ADM]]))
        return

    banido = user.get("banido", False)
    txt = (
        f"👤 *Perfil do Usuário*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: `{user['telegram_id']}`\n"
        f"📛 Username: @{user.get('username') or 'N/A'}\n"
        f"💰 Saldo: R$ {user['saldo']:.2f}\n"
        f"💸 Comissão: R$ {user['comissao']:.2f}\n"
        f"🚫 Banido: {'Sim' if banido else 'Não'}"
    )
    btns = []
    if pode(cargo, "dar_saldo"):
        btns.append([InlineKeyboardButton("💰 Dar/Remover Saldo", callback_data=f"adm_darsaldo_{uid_alvo}")])
    if pode(cargo, "banir_usuario"):
        if banido:
            btns.append([InlineKeyboardButton("✅ Desbanir", callback_data=f"adm_desbanir_{uid_alvo}")])
        else:
            btns.append([InlineKeyboardButton("🚫 Banir", callback_data=f"adm_banir_{uid_alvo}")])
    btns.append([BTN_VOLTAR_ADM])
    await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(btns), parse_mode="Markdown")


async def _executar_broadcast(bot: Bot, mensagem: str, status_msg):
    """Dispara broadcast para todos os usuários em background."""
    from database.db import listar_usuarios, total_usuarios
    total = total_usuarios()
    enviados, falhas = 0, 0
    offset = 0
    batch = 50

    while True:
        users = listar_usuarios(limit=batch, offset=offset)
        if not users:
            break
        for u in users:
            try:
                await bot.send_message(u["telegram_id"], mensagem, parse_mode="Markdown")
                enviados += 1
                await asyncio.sleep(0.05)   # respeita rate limit do Telegram
            except Exception:
                falhas += 1
        offset += batch

    try:
        await status_msg.edit_text(
            f"📢 *Broadcast concluído!*\n"
            f"✅ Enviados: {enviados}\n"
            f"❌ Falhas: {falhas}",
            parse_mode="Markdown"
        )
    except Exception:
        pass
