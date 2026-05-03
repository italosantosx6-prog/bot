"""
/pix VALOR — preferencialmente Mercado Pago (confirmação automática via API).
Fallback: PIX estático (EMV) + aprovação manual ou atalho dono.
"""
from __future__ import annotations

import asyncio
import logging
import secrets

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, ContextTypes

from config import (
    OWNER_ID,
    PIX_AUTO_APROVAR_DONO,
    PIX_KEY,
    PIX_NOTIFICAR_DONO_NOVO_PIX,
    PIX_USAR_MERCADOPAGO,
    PIX_USAR_STRIPE,
    PIX_VALOR_MIN,
)
from database.db import (
    aprovar_pagamento_se_pendente,
    atualizar_pagamento,
    get_or_create_user,
    get_pagamento,
    get_user,
    is_user_banned,
    pagar_comissao,
    registrar_pagamento,
    update_saldo,
)
from handlers.start import build_main_menu_markup, main_menu_caption
from utils.pix_generator import build_pix_payload, generate_qr_image

logger = logging.getLogger(__name__)

VALOR_MAX = 10000.0


def _novo_payment_id_estatico() -> str:
    return "p" + secrets.token_hex(10)


def _parse_valor_dos_args(args: list[str]) -> float | None:
    if not args:
        return None
    raw = " ".join(args).strip().replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        pass
    compacto = "".join(args).replace(",", ".").replace(" ", "")
    try:
        return float(compacto)
    except ValueError:
        return None


def _msg_valor_abaixo_do_minimo() -> str:
    v = PIX_VALOR_MIN
    ex = int(v) if v == int(v) else v
    return (
        f"❌ *Valor mínimo para PIX: R$ {v:.2f}*\n\n"
        "Use na mesma linha, por exemplo:\n"
        f"• `/pix {ex}` ou `/pix 15`"
    )


def _validar_valor(valor: float) -> str | None:
    if valor < PIX_VALOR_MIN:
        return _msg_valor_abaixo_do_minimo()
    if valor > VALOR_MAX:
        return "❌ Valor máximo permitido: R$ 10.000,00."
    return None


def _creditar_pix_aprovado(pid: str, uid: int, valor: float) -> bool:
    if not aprovar_pagamento_se_pendente(pid):
        return False
    update_saldo(uid, valor)
    pagar_comissao(uid, valor)
    return True


async def _store_payment_messages(context: ContextTypes.DEFAULT_TYPE, payment_id: str, messages: list):
    """Armazena mensagens relacionadas a um payment_id em bot_data para limpeza posterior."""
    store = context.application.bot_data.setdefault("pix_messages", {})
    store[payment_id] = [(m.chat.id, m.message_id) for m in messages if m]
    # métricas simples
    metrics = context.application.bot_data.setdefault("metrics", {"registered": 0, "approved": 0, "expired": 0})
    metrics["registered"] += 1


async def _delete_payment_messages(context: ContextTypes.DEFAULT_TYPE, payment_id: str):
    """Deleta mensagens anteriormente armazenadas para um pagamento."""
    store = context.application.bot_data.setdefault("pix_messages", {})
    entries = store.pop(payment_id, None)
    if not entries:
        return
    for chat_id, msg_id in entries:
        try:
            await context.bot.delete_message(chat_id, msg_id)
        except Exception:
            pass
    # não decrementamos registered; contagem de expirados/aprovados é atualizada onde aplicável


async def _expire_payment(context: ContextTypes.DEFAULT_TYPE, payment_id: str, uid: int, timeout: int = 180):
    """Aguarda `timeout` segundos; se pagamento ainda pendente, remove mensagens e marca como expired."""
    await asyncio.sleep(timeout)
    pag = get_pagamento(payment_id)
    if not pag:
        return
    status = (pag.get("status") or "").lower()
    if status == "pending":
        try:
            await _delete_payment_messages(context, payment_id)
        except Exception:
            pass
        try:
            atualizar_pagamento(payment_id, "expired")
        except Exception:
            pass
        try:
            await context.bot.send_message(
                uid,
                "⌛️ Pagamento expirado após 3 minutos. Gere outro PIX se desejar.",
                reply_markup=build_main_menu_markup(uid),
            )
        except Exception:
            pass


async def _mostrar_confirmacao_pagamento(query, uid: int, valor: float) -> None:
    await query.answer()
    user = get_user(uid)
    saldo_linha = ""
    if user:
        saldo_linha = f"\n💼 Saldo atual: *R$ {float(user['saldo']):.2f}*"
    await query.edit_message_text(
        f"✅ *Pagamento concluído!*\n\n"
        f"💰 Valor creditado: *R$ {valor:.2f}*{saldo_linha}\n\n"
        f"{main_menu_caption()}",
        reply_markup=build_main_menu_markup(uid),
        parse_mode="Markdown",
    )


async def _poll_mp_ate_aprovado(context: ContextTypes.DEFAULT_TYPE, payment_id: str, uid: int):
    """Consulta o Mercado Pago até aprovar ou esgotar tentativas (~30 min)."""
    from utils.mp_pix import consultar_status_mp

    for tentativa in range(150):
        if tentativa > 0:
            await asyncio.sleep(12)
        pag = get_pagamento(payment_id)
        if not pag:
            return
        if (pag.get("status") or "").lower() == "approved":
            return

        st = consultar_status_mp(payment_id)
        if st == "approved":
            v = float(pag["valor"])
            if _creditar_pix_aprovado(payment_id, uid, v):
                try:
                    await _delete_payment_messages(context, payment_id)
                except Exception:
                    pass
                # métricas
                m = context.application.bot_data.setdefault("metrics", {"registered": 0, "approved": 0, "expired": 0})
                m["approved"] += 1
                user = get_user(uid)
                saldo_txt = f"\n💼 Saldo: *R$ {float(user['saldo']):.2f}*" if user else ""
                await context.bot.send_message(
                    uid,
                    "✅ *Pagamento confirmado automaticamente (Mercado Pago)!*\n\n"
                    f"💰 Creditado: *R$ {v:.2f}*{saldo_txt}\n\n"
                    f"{main_menu_caption()}",
                    reply_markup=build_main_menu_markup(uid),
                    parse_mode="Markdown",
                )
            return

        if st and st != "pending":
            atualizar_pagamento(payment_id, st)
            return


async def _poll_stripe_ate_aprovado(
    context: ContextTypes.DEFAULT_TYPE, payment_id: str, uid: int
):
    from utils.stripe_pix import consultar_status_stripe

    for tentativa in range(150):
        if tentativa > 0:
            await asyncio.sleep(12)
        pag = get_pagamento(payment_id)
        if not pag:
            return
        if (pag.get("status") or "").lower() == "approved":
            return

        st = consultar_status_stripe(payment_id)
        if st == "succeeded":
            v = float(pag["valor"])
            if _creditar_pix_aprovado(payment_id, uid, v):
                try:
                    await _delete_payment_messages(context, payment_id)
                except Exception:
                    pass
                # métricas
                m = context.application.bot_data.setdefault("metrics", {"registered": 0, "approved": 0, "expired": 0})
                m["approved"] += 1
                user = get_user(uid)
                saldo_txt = f"\n💼 Saldo: *R$ {float(user['saldo']):.2f}*" if user else ""
                await context.bot.send_message(
                    uid,
                    "✅ *Pagamento confirmado (Stripe / PIX)!*\n\n"
                    f"💰 Creditado: *R$ {v:.2f}*{saldo_txt}\n\n"
                    f"{main_menu_caption()}",
                    reply_markup=build_main_menu_markup(uid),
                    parse_mode="Markdown",
                )
            return

        if st in ("canceled", "payment_failed"):
            atualizar_pagamento(payment_id, st or "cancelled")
            return


async def _enviar_pix_mp(
    update: Update, valor: float, mp_id: str, qr: str, telegram_user_id: int
 ) -> list:
    msg = update.effective_message
    if not msg:
        return []
    m1 = await msg.reply_text("⏳ Gerando PIX no Mercado Pago...")
    qr_img = generate_qr_image(qr)

    m2 = await msg.reply_photo(
        photo=qr_img,
        caption=(
            f"✅ *PIX Mercado Pago*\n\n"
            f"💰 Valor: *R$ {valor:.2f}*\n\n"
            "Pague com o QR ou o código copia e cola.\n\n"
            "🤖 O saldo *sobe sozinho* quando o MP aprovar (costuma levar segundos)."
        ),
        parse_mode="Markdown",
    )

    m3 = await msg.reply_text(
        f"`{qr}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔍 Verificar agora",
                        callback_data=f"pix_check_{mp_id}",
                    )
                ],
            ]
        ),
    )
    return [m1, m2, m3]


async def _enviar_pix_stripe(
    update: Update, valor: float, pi_id: str, qr: str, telegram_user_id: int
 ) -> list:
    msg = update.effective_message
    if not msg:
        return []

    m1 = await msg.reply_text("⏳ Gerando PIX na Stripe...")
    qr_img = generate_qr_image(qr)

    m2 = await msg.reply_photo(
        photo=qr_img,
        caption=(
            f"✅ *PIX (Stripe)*\n\n"
            f"💰 Valor: *R$ {valor:.2f}*\n\n"
            "Pague com QR ou copia e cola.\n\n"
            "🤖 O saldo *atualiza sozinho* quando o Stripe confirmar o PIX."
        ),
        parse_mode="Markdown",
    )

    m3 = await msg.reply_text(
        f"`{qr}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔍 Verificar agora",
                        callback_data=f"pix_check_{pi_id}",
                    )
                ],
            ]
        ),
    )
    return [m1, m2, m3]


async def _enviar_pix_estatico(
    update: Update, valor: float, payment_id: str, telegram_user_id: int
 ) -> list:
    msg = update.effective_message
    if not msg:
        return []

    if not (PIX_KEY or "").strip():
        await msg.reply_text(
            "❌ PIX estático não configurado (`PIX_KEY`). "
            "Ou use Stripe / Mercado Pago no `.env`."
        )
        return

    await msg.reply_text("⏳ Gerando seu PIX...")
    try:
        payload = build_pix_payload(valor)
    except ValueError as e:
        await msg.reply_text(f"❌ {e}")
        return

    qr_image = generate_qr_image(payload)

    extra = ""
    if PIX_AUTO_APROVAR_DONO and telegram_user_id == OWNER_ID:
        extra = (
            "\n\n💡 *Dono:* depois de pagar, use *Verificar pagamento* para creditar "
            "(modo estático)."
        )
    else:
        extra = (
            "\n\n⚠️ Modo estático: a loja *aprova* em `/adm` ou use *Verificar* até confirmar."
        )

    m1 = await msg.reply_photo(
        photo=qr_image,
        caption=(
            f"✅ *PIX gerado (chave da loja)*\n\n"
            f"💰 Valor: *R$ {valor:.2f}*\n\n"
            "Escaneie ou copie o código abaixo 👇"
            f"{extra}"
        ),
        parse_mode="Markdown",
    )

    m2 = await msg.reply_text(
        f"`{payload}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Verificar pagamento",
                        callback_data=f"pix_check_{payment_id}",
                    )
                ],
            ]
        ),
    )
    return [m1, m2]


async def pix_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u = update.effective_user
    get_or_create_user(u.id, u.username)
    if is_user_banned(u.id):
        await query.edit_message_text(
            "🚫 Sua conta está bloqueada.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("« Voltar", callback_data="menu_principal")]]
            ),
        )
        return

    from utils.mp_pix import mp_disponivel
    from utils.stripe_pix import stripe_disponivel

    modo = ""
    if PIX_USAR_STRIPE and stripe_disponivel():
        modo = "\n\n💳 *Stripe* — confirmação automática (PIX BRL)."
    elif PIX_USAR_MERCADOPAGO and mp_disponivel():
        modo = "\n\n🤖 *Mercado Pago* — confirmação automática."
    else:
        modo = "\n\n📌 *PIX chave / manual* — use Verificar ou /adm."

    # Menu simplificado: um único botão que pede ao usuário digitar o valor
    buttons = [
        [InlineKeyboardButton("Gerar PIX (digitar valor)", callback_data="pix_amount_custom")],
        [InlineKeyboardButton("« Voltar", callback_data="menu_principal")],
    ]

    await query.edit_message_text(
        "💳 *Gerar PIX*\n\n"
        f"Mínimo: *R$ {PIX_VALOR_MIN:.2f}*\n\n"
        "Toque em *Gerar PIX* e digite o valor em seguida."
        f"{modo}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def pix_check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    pid = query.data.replace("pix_check_", "", 1)
    uid = query.from_user.id

    if is_user_banned(uid):
        await query.answer("🚫 Conta bloqueada.", show_alert=True)
        return

    pag = get_pagamento(pid)
    if not pag:
        await query.answer("❌ Registro não encontrado.", show_alert=True)
        return

    if int(pag["telegram_id"]) != uid:
        await query.answer("❌ Este PIX não pertence a você.", show_alert=True)
        return

    status = (pag.get("status") or "").lower()
    valor = float(pag["valor"])
    es_mp = pid.isdigit()

    # Stripe (PaymentIntent)
    if status == "pending" and pid.startswith("pi_"):
        from utils.stripe_pix import consultar_status_stripe

        st_st = consultar_status_stripe(pid)
        if st_st == "succeeded":
            if _creditar_pix_aprovado(pid, uid, valor):
                await _mostrar_confirmacao_pagamento(query, uid, valor)
            else:
                pag2 = get_pagamento(pid)
                if pag2 and (pag2.get("status") or "").lower() == "approved":
                    await _mostrar_confirmacao_pagamento(
                        query, uid, float(pag2["valor"])
                    )
            return
        if st_st in ("canceled", "payment_failed"):
            atualizar_pagamento(pid, st_st)
            await query.answer(f"❌ Pagamento: {st_st}", show_alert=True)
            return
        await query.answer(
            "⏳ Ainda processando no Stripe. Pague o QR ou aguarde.",
            show_alert=True,
        )
        return

    # Mercado Pago: consulta API na hora
    if status == "pending" and es_mp:
        from utils.mp_pix import consultar_status_mp

        st_mp = consultar_status_mp(pid)
        if st_mp == "approved":
            if _creditar_pix_aprovado(pid, uid, valor):
                await _mostrar_confirmacao_pagamento(query, uid, valor)
            else:
                pag = get_pagamento(pid)
                if pag and (pag.get("status") or "").lower() == "approved":
                    await _mostrar_confirmacao_pagamento(query, uid, float(pag["valor"]))
            return
        if st_mp and st_mp != "pending":
            atualizar_pagamento(pid, st_mp)
            await query.answer(f"❌ Status no MP: {st_mp}", show_alert=True)
            return
        await query.answer(
            "⏳ Ainda pendente no Mercado Pago. Pague o QR ou aguarde alguns segundos.",
            show_alert=True,
        )
        return

    # Estático: dono pode confirmar rápido
    if (
        status == "pending"
        and not es_mp
        and PIX_AUTO_APROVAR_DONO
        and uid == OWNER_ID
        and aprovar_pagamento_se_pendente(pid)
    ):
        update_saldo(uid, valor)
        pagar_comissao(uid, valor)
        await _mostrar_confirmacao_pagamento(query, uid, valor)
        return

    pag = get_pagamento(pid)
    if not pag:
        await query.answer("❌ Registro não encontrado.", show_alert=True)
        return
    status = (pag.get("status") or "").lower()
    valor = float(pag["valor"])

    if status == "pending" and not es_mp:
        expl_key = f"pix_explicado_{pid}"
        if not context.user_data.get(expl_key):
            context.user_data[expl_key] = True
            await query.answer()
            await query.message.reply_text(
                "⏳ *PIX estático — ainda não creditado*\n\n"
                "Peça à loja para aprovar em `/adm` → *PIX Pendentes*, "
                "ou use *Verificar* de novo depois.\n\n"
                f"Valor: *R$ {valor:.2f}* · ID: `{pid}`",
                parse_mode="Markdown",
            )
        else:
            await query.answer(
                "⏳ Pendente de aprovação da loja.",
                show_alert=True,
            )
        return

    if status == "approved":
        await _mostrar_confirmacao_pagamento(query, uid, float(pag["valor"]))
        return

    await query.answer(
        "❌ PIX encerrado. Gere outro com `/pix VALOR`.",
        show_alert=True,
    )


async def pix_amount_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para seleção rápida de valores via botões."""
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if is_user_banned(uid):
        await query.answer("🚫 Conta bloqueada.", show_alert=True)
        return

    data = query.data.replace("pix_amount_", "", 1)
    if data == "custom":
        # Entrar em modo de espera para receber valor digitado pelo usuário
        context.user_data["awaiting_pix_amount"] = True
        await query.message.reply_text(
            f"✏️ Digite o valor que deseja depositar (mínimo R$ {PIX_VALOR_MIN:.2f}):",
            parse_mode="Markdown",
        )
        return

    try:
        valor = float(data)
    except ValueError:
        await query.answer("Valor inválido.", show_alert=True)
        return

    err = _validar_valor(valor)
    if err:
        await query.answer(err, show_alert=True)
        return

    # Reaproveitar lógica de criação de cobrança do comando /pix
    get_or_create_user(uid, query.from_user.username)

    from utils.mp_pix import criar_cobranca_pix_mp, mp_disponivel
    from utils.stripe_pix import criar_pix_stripe, stripe_disponivel

    if PIX_USAR_STRIPE and stripe_disponivel():
        try:
            pi_id, qr = criar_pix_stripe(uid, valor)
            registrar_pagamento(uid, pi_id, valor, "pending")
            asyncio.create_task(_poll_stripe_ate_aprovado(context, pi_id, uid))
            msgs = await _enviar_pix_stripe(update, valor, pi_id, qr, uid)
            await _store_payment_messages(context, pi_id, msgs)
            asyncio.create_task(_expire_payment(context, pi_id, uid, 180))
            return
        except RuntimeError as e:
            logger.warning("Stripe indisponível, tentando MP/estático: %s", e)

    use_mp = PIX_USAR_MERCADOPAGO and mp_disponivel()

    if use_mp:
        try:
            mp_id, qr = criar_cobranca_pix_mp(uid, valor)
            registrar_pagamento(uid, mp_id, valor, "pending")
            asyncio.create_task(_poll_mp_ate_aprovado(context, mp_id, uid))
            msgs = await _enviar_pix_mp(update, valor, mp_id, qr, uid)
            await _store_payment_messages(context, mp_id, msgs)
            asyncio.create_task(_expire_payment(context, mp_id, uid, 180))
            return
        except RuntimeError as e:
            logger.warning("Mercado Pago indisponível, tentando estático: %s", e)

    if not (PIX_KEY or "").strip():
        await query.message.reply_text(
            "❌ Configure `STRIPE_SECRET_KEY`, ou `MP_ACCESS_TOKEN`, ou `PIX_KEY` no `.env`.",
        )
        return

    payment_id = _novo_payment_id_estatico()
    registrar_pagamento(uid, payment_id, valor, "pending")

    if PIX_NOTIFICAR_DONO_NOVO_PIX and OWNER_ID and uid != OWNER_ID:
        try:
            await context.bot.send_message(
                OWNER_ID,
                "💳 *PIX pendente (estático)*\n\n"
                f"R$ {valor:.2f} · `{uid}` · `{payment_id}`\n"
                "`/adm` → PIX Pendentes",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    msgs = await _enviar_pix_estatico(update, valor, payment_id, uid)
    await _store_payment_messages(context, payment_id, msgs)
    asyncio.create_task(_expire_payment(context, payment_id, uid, 180))


async def pix_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = list(context.args or [])
    u = update.effective_user

    if is_user_banned(u.id):
        await update.effective_message.reply_text("🚫 Sua conta está bloqueada.")
        return

    if not args:
        await update.effective_message.reply_text(
            "⚠️ Use *na mesma linha*: `/pix VALOR`\n\n"
            f"Ex.: `/pix 1` • `/pix 10` (mín. R$ {PIX_VALOR_MIN:.2f})",
            parse_mode="Markdown",
        )
        return

    valor = _parse_valor_dos_args(args)
    if valor is None:
        await update.effective_message.reply_text(
            "❌ Valor inválido. Ex: `/pix 10` ou `/pix 1,50`",
            parse_mode="Markdown",
        )
        return

    err = _validar_valor(valor)
    if err:
        await update.effective_message.reply_text(err, parse_mode="Markdown")
        return

    get_or_create_user(u.id, u.username)

    from utils.mp_pix import criar_cobranca_pix_mp, mp_disponivel
    from utils.stripe_pix import criar_pix_stripe, stripe_disponivel

    if PIX_USAR_STRIPE and stripe_disponivel():
        try:
            pi_id, qr = criar_pix_stripe(u.id, valor)
            registrar_pagamento(u.id, pi_id, valor, "pending")
            asyncio.create_task(_poll_stripe_ate_aprovado(context, pi_id, u.id))
            msgs = await _enviar_pix_stripe(update, valor, pi_id, qr, u.id)
            await _store_payment_messages(context, pi_id, msgs)
            asyncio.create_task(_expire_payment(context, pi_id, u.id, 180))
            return
        except RuntimeError as e:
            logger.warning("Stripe indisponível, tentando MP/estático: %s", e)
            if not PIX_USAR_MERCADOPAGO and not (PIX_KEY or "").strip():
                await update.effective_message.reply_text(
                    f"❌ Stripe falhou: {e}\n\n"
                    "Defina `STRIPE_SECRET_KEY` (sk_live_ ou sk_test_) ou use MP / PIX_KEY.",
                )
                return

    use_mp = PIX_USAR_MERCADOPAGO and mp_disponivel()

    if use_mp:
        try:
            mp_id, qr = criar_cobranca_pix_mp(u.id, valor)
            registrar_pagamento(u.id, mp_id, valor, "pending")
            asyncio.create_task(_poll_mp_ate_aprovado(context, mp_id, u.id))
            msgs = await _enviar_pix_mp(update, valor, mp_id, qr, u.id)
            await _store_payment_messages(context, mp_id, msgs)
            asyncio.create_task(_expire_payment(context, mp_id, u.id, 180))
            return
        except RuntimeError as e:
            logger.warning("Mercado Pago indisponível, tentando estático: %s", e)
            if not (PIX_KEY or "").strip():
                await update.effective_message.reply_text(
                    f"❌ Mercado Pago falhou: {e}\n\n"
                    "Cadastre `PIX_KEY` para PIX estático ou corrija o token MP.",
                )
                return

    if not (PIX_KEY or "").strip():
        await update.effective_message.reply_text(
            "❌ Configure `STRIPE_SECRET_KEY`, ou `MP_ACCESS_TOKEN`, ou `PIX_KEY` no `.env`.",
        )
        return

    payment_id = _novo_payment_id_estatico()
    registrar_pagamento(u.id, payment_id, valor, "pending")

    if PIX_NOTIFICAR_DONO_NOVO_PIX and OWNER_ID and u.id != OWNER_ID:
        try:
            await context.bot.send_message(
                OWNER_ID,
                "💳 *PIX pendente (estático)*\n\n"
                f"R$ {valor:.2f} · `{u.id}` · `{payment_id}`\n"
                "`/adm` → PIX Pendentes",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    msgs = await _enviar_pix_estatico(update, valor, payment_id, u.id)
    await _store_payment_messages(context, payment_id, msgs)
    asyncio.create_task(_expire_payment(context, payment_id, u.id, 180))


pix_handler = CommandHandler("pix", pix_command)


async def handle_custom_amount_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Captura mensagem de texto quando aguardamos um valor customizado."""
    if not context.user_data.get("awaiting_pix_amount"):
        return

    msg = update.effective_message
    if not msg or not msg.text:
        return False

    text = msg.text.strip()
    # Tenta extrair número (aceita vírgula como separador)
    try:
        raw = text.replace("R$", "").replace("r$", "").replace(",", ".").strip()
        valor = float(raw)
    except Exception:
        await msg.reply_text("❌ Valor inválido. Digite o valor em reais, ex.: 15 ou 15,50")
        return True

    err = _validar_valor(valor)
    if err:
        await msg.reply_text(err, parse_mode="Markdown")
        return True

    uid = update.effective_user.id
    # limpar flag
    context.user_data.pop("awaiting_pix_amount", None)

    # Reaproveitar a lógica de geração de cobrança do botão
    from utils.mp_pix import criar_cobranca_pix_mp, mp_disponivel
    from utils.stripe_pix import criar_pix_stripe, stripe_disponivel

    if PIX_USAR_STRIPE and stripe_disponivel():
        try:
            pi_id, qr = criar_pix_stripe(uid, valor)
            registrar_pagamento(uid, pi_id, valor, "pending")
            asyncio.create_task(_poll_stripe_ate_aprovado(context, pi_id, uid))
            msgs = await _enviar_pix_stripe(update, valor, pi_id, qr, uid)
            await _store_payment_messages(context, pi_id, msgs)
            asyncio.create_task(_expire_payment(context, pi_id, uid, 180))
            return True
        except RuntimeError as e:
            logger.warning("Stripe indisponível, tentando MP/estático: %s", e)

    use_mp = PIX_USAR_MERCADOPAGO and mp_disponivel()
    if use_mp:
        try:
            mp_id, qr = criar_cobranca_pix_mp(uid, valor)
            registrar_pagamento(uid, mp_id, valor, "pending")
            asyncio.create_task(_poll_mp_ate_aprovado(context, mp_id, uid))
            msgs = await _enviar_pix_mp(update, valor, mp_id, qr, uid)
            await _store_payment_messages(context, mp_id, msgs)
            asyncio.create_task(_expire_payment(context, mp_id, uid, 180))
            return True
        except RuntimeError as e:
            logger.warning("Mercado Pago indisponível, tentando estático: %s", e)

    if not (PIX_KEY or "").strip():
        await msg.reply_text(
            "❌ Configure `STRIPE_SECRET_KEY`, ou `MP_ACCESS_TOKEN`, ou `PIX_KEY` no `.env`.",
        )
        return True

    payment_id = _novo_payment_id_estatico()
    registrar_pagamento(uid, payment_id, valor, "pending")

    if PIX_NOTIFICAR_DONO_NOVO_PIX and OWNER_ID and uid != OWNER_ID:
        try:
            await context.bot.send_message(
                OWNER_ID,
                "💳 *PIX pendente (estático)*\n\n"
                f"R$ {valor:.2f} · `{uid}` · `{payment_id}`\n"
                "`/adm` → PIX Pendentes",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    msgs = await _enviar_pix_estatico(update, valor, payment_id, uid)
    await _store_payment_messages(context, payment_id, msgs)
    asyncio.create_task(_expire_payment(context, payment_id, uid, 180))
    return True
