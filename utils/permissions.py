"""
utils/permissions.py
Sistema de cargos: DONO > ADMIN > MODERADOR > REVENDEDOR

Permissões por cargo:
  DONO       — tudo, incluindo dar/remover cargos e ver o OWNER_ID
  ADMIN      — add produtos, stats, gerenciar usuários, broadcast, PIX
  MODERADOR  — banir usuários, ver stats, ver perfis
  REVENDEDOR — adicionar produtos apenas
"""
import functools
from enum import IntEnum
from telegram import Update
from telegram.ext import ContextTypes
from config import OWNER_ID

# ─── Níveis ────────────────────────────────────────────────────────────────
class Cargo(IntEnum):
    REVENDEDOR = 1
    MODERADOR  = 2
    ADMIN      = 3
    DONO       = 99   # só o OWNER_ID recebe isso

# Permissões por cargo (o que cada um PODE fazer)
PERMISSOES: dict[Cargo, set[str]] = {
    Cargo.REVENDEDOR: {
        "add_produtos",
    },
    Cargo.MODERADOR: {
        "add_produtos",
        "ver_stats",
        "ver_perfil_usuario",
        "banir_usuario",
    },
    Cargo.ADMIN: {
        "add_produtos",
        "ver_stats",
        "ver_perfil_usuario",
        "banir_usuario",
        "dar_saldo",
        "broadcast",
        "ver_pagamentos",
        "cancelar_pagamento",
        "gerenciar_gift",
    },
    Cargo.DONO: {
        "add_produtos",
        "ver_stats",
        "ver_perfil_usuario",
        "banir_usuario",
        "dar_saldo",
        "broadcast",
        "ver_pagamentos",
        "cancelar_pagamento",
        "dar_cargo",
        "remover_cargo",
        "ver_admins",
        "remover_produto",
        "gerenciar_gift",
    },
}


def pode(cargo: Cargo | None, permissao: str) -> bool:
    """Retorna True se o cargo tem a permissão solicitada."""
    if cargo is None:
        return False
    return permissao in PERMISSOES.get(cargo, set())


def get_cargo_db(telegram_id: int) -> Cargo | None:
    """Busca o cargo do usuário no banco. Dono sempre retorna DONO."""
    if telegram_id == OWNER_ID:
        return Cargo.DONO
    from database.db import get_staff_member
    staff = get_staff_member(telegram_id)
    if not staff:
        return None
    return Cargo(staff["cargo"])


def cargo_nome(cargo: Cargo) -> str:
    nomes = {
        Cargo.DONO:       "👑 Dono",
        Cargo.ADMIN:      "🔴 Admin",
        Cargo.MODERADOR:  "🟡 Moderador",
        Cargo.REVENDEDOR: "🟢 Revendedor",
    }
    return nomes.get(cargo, "❓ Desconhecido")


# ─── Decorators ────────────────────────────────────────────────────────────
def requer_cargo(permissao: str):
    """
    Decorator para handlers de callback e comando.
    Uso: @requer_cargo("ver_stats")
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            uid = update.effective_user.id
            cargo = get_cargo_db(uid)
            if not pode(cargo, permissao):
                msg = "🚫 *Acesso negado.*\nVocê não tem permissão para isso."
                if update.callback_query:
                    await update.callback_query.answer("🚫 Sem permissão.", show_alert=True)
                else:
                    await update.message.reply_text(msg, parse_mode="Markdown")
                return
            context.user_data["_cargo"] = cargo
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator


def requer_dono():
    """Decorator exclusivo para o dono."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            uid = update.effective_user.id
            if uid != OWNER_ID:
                if update.callback_query:
                    await update.callback_query.answer("👑 Apenas o dono pode fazer isso.", show_alert=True)
                else:
                    await update.message.reply_text("👑 *Apenas o dono pode usar este comando.*", parse_mode="Markdown")
                return
            context.user_data["_cargo"] = Cargo.DONO
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator
