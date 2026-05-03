"""
handlers/inline_search.py

Inline Mode do Telegram — quando o usuário clica em
"Buscar banco/bin/bandeira" o bot preenche automaticamente
@nomebot buscar_banco no campo de mensagem e conforme ele
digita aparecem os resultados em tempo real em cima do teclado.

⚙️  Para ativar: fale com @BotFather → /setinline → coloque
    o placeholder: "buscar_banco BANCO DO BRASIL"
"""
from telegram import (
    Update,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import ContextTypes
from database.db import listar_gggs, listar_ccs
from config import PRECO_GGG_UNITARIA, PRECO_CC_UNITARIA
import hashlib


# ── Helpers ──────────────────────────────────────────────────────────────────

def _uid(seed: str) -> str:
    """Gera um ID único determinístico para o InlineQueryResult."""
    return hashlib.md5(seed.encode()).hexdigest()[:16]


def _card_masked(numero: str) -> str:
    if len(numero) > 6:
        return numero[:6] + "*" * (len(numero) - 6)
    return numero


# ── Handler principal ─────────────────────────────────────────────────────────

async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query
    if not query:
        return

    texto = query.query.strip()
    resultados = []

    # ── buscar_banco ─────────────────────────────────────────────────────────
    if texto.lower().startswith("buscar_banco"):
        partes = texto.split(None, 1)
        valor = partes[1].strip() if len(partes) > 1 else ""

        itens = listar_gggs({"banco": valor}) if valor else listar_gggs()
        for item in itens[:30]:
            numero_masked = _card_masked(item.get("numero", ""))
            titulo  = f"🏦 {item.get('banco','?')} — {item.get('bandeira','?')} — R$ {PRECO_GGG_UNITARIA:.0f}"
            descr   = f"Cartão: {numero_masked} | Validade: {item.get('validade','?')} | BIN: {item.get('bin','?')}"

            resultados.append(InlineQueryResultArticle(
                id          = _uid(f"ggg_{item['id']}"),
                title       = titulo,
                description = descr,
                thumbnail_url = "https://i.imgur.com/3ZtEEkr.png",
                input_message_content=InputTextMessageContent(
                    f"🔑 GGG selecionado:\n"
                    f"🏦 Banco: {item.get('banco','?')}\n"
                    f"💳 Cartão: `{numero_masked}`\n"
                    f"📅 Validade: {item.get('validade','?')}\n"
                    f"🔢 BIN: {item.get('bin','?')}\n"
                    f"🏳 Bandeira: {item.get('bandeira','?')}\n"
                    f"💰 Preço: R$ {PRECO_GGG_UNITARIA:.2f}",
                    parse_mode="Markdown"
                ),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "✅ Comprar este GGG",
                        callback_data=f"ggs_comprar_{item['id']}"
                    )
                ]])
            ))

    # ── buscar_bin ───────────────────────────────────────────────────────────
    elif texto.lower().startswith("buscar_bin"):
        partes = texto.split(None, 1)
        valor = partes[1].strip() if len(partes) > 1 else ""

        itens = listar_gggs({"bin": valor}) if valor else listar_gggs()
        for item in itens[:30]:
            numero_masked = _card_masked(item.get("numero", ""))
            titulo  = f"🔑 BIN {item.get('bin','?')} — {item.get('banco','?')} — R$ {PRECO_GGG_UNITARIA:.0f}"
            descr   = f"Cartão: {numero_masked} | {item.get('bandeira','?')} | Validade: {item.get('validade','?')}"

            resultados.append(InlineQueryResultArticle(
                id          = _uid(f"ggg_bin_{item['id']}"),
                title       = titulo,
                description = descr,
                thumbnail_url = "https://i.imgur.com/3ZtEEkr.png",
                input_message_content=InputTextMessageContent(
                    f"🔑 GGG por BIN:\n"
                    f"🔢 BIN: {item.get('bin','?')}\n"
                    f"🏦 Banco: {item.get('banco','?')}\n"
                    f"💳 Cartão: `{numero_masked}`\n"
                    f"📅 Validade: {item.get('validade','?')}\n"
                    f"🏳 Bandeira: {item.get('bandeira','?')}\n"
                    f"💰 Preço: R$ {PRECO_GGG_UNITARIA:.2f}",
                    parse_mode="Markdown"
                ),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "✅ Comprar este GGG",
                        callback_data=f"ggs_comprar_{item['id']}"
                    )
                ]])
            ))

    # ── buscar_bandeira ───────────────────────────────────────────────────────
    elif texto.lower().startswith("buscar_bandeira"):
        partes = texto.split(None, 1)
        valor = partes[1].strip() if len(partes) > 1 else ""

        itens = listar_gggs({"bandeira": valor}) if valor else listar_gggs()
        for item in itens[:30]:
            numero_masked = _card_masked(item.get("numero", ""))
            titulo  = f"🏳 {item.get('bandeira','?')} — {item.get('banco','?')} — R$ {PRECO_GGG_UNITARIA:.0f}"
            descr   = f"Cartão: {numero_masked} | BIN: {item.get('bin','?')} | Validade: {item.get('validade','?')}"

            resultados.append(InlineQueryResultArticle(
                id          = _uid(f"ggg_band_{item['id']}"),
                title       = titulo,
                description = descr,
                thumbnail_url = "https://i.imgur.com/3ZtEEkr.png",
                input_message_content=InputTextMessageContent(
                    f"🔑 GGG por Bandeira:\n"
                    f"🏳 Bandeira: {item.get('bandeira','?')}\n"
                    f"🏦 Banco: {item.get('banco','?')}\n"
                    f"💳 Cartão: `{numero_masked}`\n"
                    f"📅 Validade: {item.get('validade','?')}\n"
                    f"🔢 BIN: {item.get('bin','?')}\n"
                    f"💰 Preço: R$ {PRECO_GGG_UNITARIA:.2f}",
                    parse_mode="Markdown"
                ),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "✅ Comprar este GGG",
                        callback_data=f"ggs_comprar_{item['id']}"
                    )
                ]])
            ))

    # ── cc_buscar_banco ───────────────────────────────────────────────────────
    elif texto.lower().startswith("cc_buscar_banco"):
        partes = texto.split(None, 1)
        valor = partes[1].strip() if len(partes) > 1 else ""

        itens = listar_ccs({"banco": valor}) if valor else listar_ccs()
        for item in itens[:30]:
            numero_masked = _card_masked(item.get("numero", ""))
            titulo  = f"💳 CC {item.get('banco','?')} — {item.get('bandeira','?')} — R$ {PRECO_CC_UNITARIA:.0f}"
            descr   = f"Cartão: {numero_masked} | Validade: {item.get('validade','?')} | BIN: {item.get('bin','?')}"

            resultados.append(InlineQueryResultArticle(
                id          = _uid(f"cc_banco_{item['id']}"),
                title       = titulo,
                description = descr,
                thumbnail_url = "https://i.imgur.com/K6kNb9N.png",
                input_message_content=InputTextMessageContent(
                    f"💳 CC por Banco:\n"
                    f"🏦 Banco: {item.get('banco','?')}\n"
                    f"💳 Cartão: `{numero_masked}`\n"
                    f"📅 Validade: {item.get('validade','?')}\n"
                    f"🔢 BIN: {item.get('bin','?')}\n"
                    f"🏳 Bandeira: {item.get('bandeira','?')}\n"
                    f"💰 Preço: R$ {PRECO_CC_UNITARIA:.2f}",
                    parse_mode="Markdown"
                ),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "✅ Comprar esta CC",
                        callback_data=f"cc_comprar_{item['id']}"
                    )
                ]])
            ))

    # ── cc_buscar_bin ─────────────────────────────────────────────────────────
    elif texto.lower().startswith("cc_buscar_bin"):
        partes = texto.split(None, 1)
        valor = partes[1].strip() if len(partes) > 1 else ""

        itens = listar_ccs({"bin": valor}) if valor else listar_ccs()
        for item in itens[:30]:
            numero_masked = _card_masked(item.get("numero", ""))
            titulo  = f"💳 CC BIN {item.get('bin','?')} — {item.get('banco','?')} — R$ {PRECO_CC_UNITARIA:.0f}"
            descr   = f"Cartão: {numero_masked} | {item.get('bandeira','?')} | Validade: {item.get('validade','?')}"

            resultados.append(InlineQueryResultArticle(
                id          = _uid(f"cc_bin_{item['id']}"),
                title       = titulo,
                description = descr,
                thumbnail_url = "https://i.imgur.com/K6kNb9N.png",
                input_message_content=InputTextMessageContent(
                    f"💳 CC por BIN:\n"
                    f"🔢 BIN: {item.get('bin','?')}\n"
                    f"🏦 Banco: {item.get('banco','?')}\n"
                    f"💳 Cartão: `{numero_masked}`\n"
                    f"📅 Validade: {item.get('validade','?')}\n"
                    f"🏳 Bandeira: {item.get('bandeira','?')}\n"
                    f"💰 Preço: R$ {PRECO_CC_UNITARIA:.2f}",
                    parse_mode="Markdown"
                ),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "✅ Comprar esta CC",
                        callback_data=f"cc_comprar_{item['id']}"
                    )
                ]])
            ))

    # ── cc_buscar_bandeira ────────────────────────────────────────────────────
    elif texto.lower().startswith("cc_buscar_bandeira"):
        partes = texto.split(None, 1)
        valor = partes[1].strip() if len(partes) > 1 else ""

        itens = listar_ccs({"bandeira": valor}) if valor else listar_ccs()
        for item in itens[:30]:
            numero_masked = _card_masked(item.get("numero", ""))
            titulo  = f"💳 CC {item.get('bandeira','?')} — {item.get('banco','?')} — R$ {PRECO_CC_UNITARIA:.0f}"
            descr   = f"Cartão: {numero_masked} | BIN: {item.get('bin','?')} | Validade: {item.get('validade','?')}"

            resultados.append(InlineQueryResultArticle(
                id          = _uid(f"cc_band_{item['id']}"),
                title       = titulo,
                description = descr,
                thumbnail_url = "https://i.imgur.com/K6kNb9N.png",
                input_message_content=InputTextMessageContent(
                    f"💳 CC por Bandeira:\n"
                    f"🏳 Bandeira: {item.get('bandeira','?')}\n"
                    f"🏦 Banco: {item.get('banco','?')}\n"
                    f"💳 Cartão: `{numero_masked}`\n"
                    f"📅 Validade: {item.get('validade','?')}\n"
                    f"🔢 BIN: {item.get('bin','?')}\n"
                    f"💰 Preço: R$ {PRECO_CC_UNITARIA:.2f}",
                    parse_mode="Markdown"
                ),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "✅ Comprar esta CC",
                        callback_data=f"cc_comprar_{item['id']}"
                    )
                ]])
            ))

    # ── Sem resultados ────────────────────────────────────────────────────────
    if not resultados and texto:
        resultados.append(InlineQueryResultArticle(
            id    = "nenhum",
            title = "😔 Nenhum resultado encontrado",
            description = f"Busca: {texto}",
            input_message_content=InputTextMessageContent("Nenhum item encontrado para sua busca."),
        ))

    await query.answer(
        resultados,
        cache_time=10,          # segundos que o Telegram cacheia o resultado
        is_personal=True,       # cache separado por usuário
    )
