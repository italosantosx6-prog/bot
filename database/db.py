"""
database/db.py
Toda interação com o Supabase fica aqui.
"""
import logging
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY, COMISSAO_INDICACAO

logger = logging.getLogger(__name__)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ── Usuários ─────────────────────────────────────────────────────────────────

def get_or_create_user(telegram_id: int, username: str = None, ref_id: int = None) -> dict:
    """
    Identifica o cliente pelo Telegram ID (único por conta).
    Cria linha na primeira vez; atualiza username quando mudar no Telegram.
    """
    res = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
    if res.data:
        row = res.data[0]
        nu = (username or "").strip()
        if nu and row.get("username") != nu:
            supabase.table("users").update({"username": nu}).eq("telegram_id", telegram_id).execute()
            row["username"] = nu
        return row

    payload = {
        "telegram_id": telegram_id,
        "username": (username or "").strip(),
        "saldo": 0.0,
        "comissao": 0.0,
        "referido_por": ref_id,
    }
    ins = supabase.table("users").insert(payload).execute()
    return ins.data[0]


def get_user(telegram_id: int) -> dict | None:
    res = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
    return res.data[0] if res.data else None


def update_saldo(telegram_id: int, valor: float):
    user = get_user(telegram_id)
    if not user:
        return
    antigo = float(user.get("saldo") or 0.0)
    novo = round(antigo + valor, 2)
    logger.info("update_saldo: telegram_id=%s antigo=%s adicionar=%s novo=%s",
                telegram_id, antigo, valor, novo)
    supabase.table("users").update({"saldo": novo}).eq("telegram_id", telegram_id).execute()


def debitar_saldo_se_suficiente(telegram_id: int, valor: float, tentativas: int = 3) -> bool:
    """
    Debita saldo com proteção contra corrida.
    Retorna True se debitou, False se saldo insuficiente/concorrência.
    """
    if valor <= 0:
        logger.warning("debitar_saldo_se_suficiente: valor invalido %s", valor)
        return False

    for tentativa in range(1, tentativas + 1):
        user = get_user(telegram_id)
        if not user:
            return False
        saldo_atual = float(user.get("saldo") or 0.0)
        if saldo_atual < valor:
            logger.info("debitar_saldo: telegram_id=%s saldo_atual=%s menor que valor=%s", telegram_id, saldo_atual, valor)
            return False

        novo = round(saldo_atual - valor, 2)
        res = (
            supabase.table("users")
            .update({"saldo": novo})
            .eq("telegram_id", telegram_id)
            .eq("saldo", saldo_atual)
            .execute()
        )
        if res.data:
            logger.info("debitar_saldo: telegram_id=%s tentativas=%s -> sucesso", telegram_id, tentativa)
            return True
        else:
            logger.warning("debitar_saldo: telegram_id=%s tentativas=%s -> concorrencia, retry", telegram_id, tentativa)
    return False


def pagar_comissao(comprador_id: int, valor_pago: float):
    """Credita comissão ao referidor quando comprador recarrega."""
    user = get_user(comprador_id)
    if not user or not user.get("referido_por"):
        return
    comissao = round(valor_pago * COMISSAO_INDICACAO, 2)
    ref_id = user["referido_por"]
    ref = get_user(ref_id)
    if ref:
        nova_com = round(ref["comissao"] + comissao, 2)
        logger.info("pagar_comissao: comprador=%s ref=%s valor_pago=%s comissao=%s nova_com=%s",
                    comprador_id, ref_id, valor_pago, comissao, nova_com)
        supabase.table("users").update({"comissao": nova_com}).eq("telegram_id", ref_id).execute()


def trocar_comissao_por_saldo(telegram_id: int) -> float:
    """Transfere saldo de comissão para saldo principal."""
    user = get_user(telegram_id)
    if not user or user["comissao"] <= 0:
        return 0.0
    valor = user["comissao"]
    novo_saldo = round(user["saldo"] + valor, 2)
    logger.info("trocar_comissao_por_saldo: telegram_id=%s comissao=%s novo_saldo=%s",
                telegram_id, valor, novo_saldo)
    supabase.table("users").update({
        "saldo": novo_saldo, "comissao": 0.0
    }).eq("telegram_id", telegram_id).execute()
    return valor


# ── GGGs ─────────────────────────────────────────────────────────────────────

def listar_gggs(filtro: dict = None) -> list:
    q = supabase.table("gggs").select("*").eq("vendido", False)
    if filtro:
        for k, v in filtro.items():
            q = q.ilike(k, f"%{v}%")
    return q.execute().data


def get_ggg(ggg_id: int) -> dict | None:
    res = supabase.table("gggs").select("*").eq("id", ggg_id).execute()
    return res.data[0] if res.data else None


def marcar_ggg_vendido(ggg_id: int, comprador_id: int):
    supabase.table("gggs").update({
        "vendido": True, "comprador_id": comprador_id
    }).eq("id", ggg_id).execute()


def marcar_ggg_vendido_se_disponivel(ggg_id: int, comprador_id: int) -> bool:
    """
    Marca como vendido somente se ainda estiver disponível.
    """
    res = (
        supabase.table("gggs")
        .update({"vendido": True, "comprador_id": comprador_id})
        .eq("id", ggg_id)
        .eq("vendido", False)
        .execute()
    )
    return bool(res.data)


def adicionar_ggg(dados: dict) -> dict:
    return supabase.table("gggs").insert(dados).execute().data[0]


# ── CCs ──────────────────────────────────────────────────────────────────────

def listar_ccs(filtro: dict = None) -> list:
    q = supabase.table("ccs").select("*").eq("vendido", False)
    if filtro:
        for k, v in filtro.items():
            q = q.ilike(k, f"%{v}%")
    return q.execute().data


def get_cc(cc_id: int) -> dict | None:
    res = supabase.table("ccs").select("*").eq("id", cc_id).execute()
    return res.data[0] if res.data else None


def marcar_cc_vendida(cc_id: int, comprador_id: int):
    supabase.table("ccs").update({
        "vendido": True, "comprador_id": comprador_id
    }).eq("id", cc_id).execute()


def marcar_cc_vendida_se_disponivel(cc_id: int, comprador_id: int) -> bool:
    """
    Marca como vendida somente se ainda estiver disponível.
    """
    res = (
        supabase.table("ccs")
        .update({"vendido": True, "comprador_id": comprador_id})
        .eq("id", cc_id)
        .eq("vendido", False)
        .execute()
    )
    return bool(res.data)


def adicionar_cc(dados: dict) -> dict:
    return supabase.table("ccs").insert(dados).execute().data[0]


# ── Logins ───────────────────────────────────────────────────────────────────

def listar_logins() -> list:
    return supabase.table("logins").select("*").eq("vendido", False).execute().data


def get_login(login_id: int) -> dict | None:
    res = supabase.table("logins").select("*").eq("id", login_id).execute()
    return res.data[0] if res.data else None


def marcar_login_vendido(login_id: int, comprador_id: int):
    supabase.table("logins").update({
        "vendido": True, "comprador_id": comprador_id
    }).eq("id", login_id).execute()


def marcar_login_vendido_se_disponivel(login_id: int, comprador_id: int) -> bool:
    """
    Marca login como vendido somente se ainda estiver disponível.
    """
    res = (
        supabase.table("logins")
        .update({"vendido": True, "comprador_id": comprador_id})
        .eq("id", login_id)
        .eq("vendido", False)
        .execute()
    )
    return bool(res.data)


def adicionar_login(dados: dict) -> dict:
    return supabase.table("logins").insert(dados).execute().data[0]


# ── Histórico de compras ──────────────────────────────────────────────────────

def registrar_compra(telegram_id: int, tipo: str, item_id: int, valor: float):
    supabase.table("historico").insert({
        "telegram_id": telegram_id,
        "tipo": tipo,
        "item_id": item_id,
        "valor": valor,
    }).execute()


def historico_usuario(telegram_id: int) -> list:
    return supabase.table("historico").select("*") \
        .eq("telegram_id", telegram_id) \
        .order("created_at", desc=True) \
        .limit(20) \
        .execute().data


# ── Pagamentos PIX ────────────────────────────────────────────────────────────

def registrar_pagamento(telegram_id: int, payment_id: str, valor: float, status: str = "pending"):
    logger.info("registrar_pagamento: telegram_id=%s payment_id=%s valor=%s status=%s",
                telegram_id, payment_id, valor, status)
    supabase.table("pagamentos").insert({
        "telegram_id": telegram_id,
        "payment_id": payment_id,
        "valor": valor,
        "status": status,
    }).execute()


def atualizar_pagamento(payment_id: str, status: str):
    logger.info("atualizar_pagamento: payment_id=%s -> %s", payment_id, status)
    supabase.table("pagamentos").update({"status": status}).eq("payment_id", payment_id).execute()


def aprovar_pagamento_se_pendente(payment_id: str) -> bool:
    """
    Aprova somente se ainda estiver pending.
    Evita crédito duplicado em corrida entre verificações.
    """
    logger.info("aprovar_pagamento_se_pendente: payment_id=%s", payment_id)
    res = (
        supabase.table("pagamentos")
        .update({"status": "approved"})
        .eq("payment_id", payment_id)
        .eq("status", "pending")
        .execute()
    )
    ok = bool(res.data)
    logger.info("aprovar_pagamento_se_pendente: payment_id=%s approved=%s", payment_id, ok)
    return ok


def get_pagamento(payment_id: str) -> dict | None:
    res = supabase.table("pagamentos").select("*").eq("payment_id", payment_id).execute()
    return res.data[0] if res.data else None


def listar_pagamentos_pendentes() -> list:
    return supabase.table("pagamentos").select("*") \
        .eq("status", "pending") \
        .order("created_at", desc=True) \
        .limit(30) \
        .execute().data


def cancelar_pagamento_db(payment_id: str):
    logger.info("cancelar_pagamento_db: payment_id=%s", payment_id)
    supabase.table("pagamentos").update({"status": "cancelled"}).eq("payment_id", payment_id).execute()


# ── Staff / Cargos ────────────────────────────────────────────────────────────

def get_staff_member(telegram_id: int) -> dict | None:
    res = supabase.table("staff").select("*").eq("telegram_id", telegram_id).execute()
    return res.data[0] if res.data else None


def listar_staff() -> list:
    return supabase.table("staff").select("*").order("cargo", desc=True).execute().data


def adicionar_staff(telegram_id: int, username: str, cargo: int, dado_por: int) -> dict:
    # Remove cargo antigo se existir
    supabase.table("staff").delete().eq("telegram_id", telegram_id).execute()
    res = supabase.table("staff").insert({
        "telegram_id": telegram_id,
        "username": username,
        "cargo": cargo,
        "dado_por": dado_por,
    }).execute()
    return res.data[0]


def remover_staff(telegram_id: int):
    supabase.table("staff").delete().eq("telegram_id", telegram_id).execute()


# ── Gestão de Usuários ────────────────────────────────────────────────────────

def banir_usuario(telegram_id: int, banido_por: int):
    supabase.table("users").update({
        "banido": True, "banido_por": banido_por
    }).eq("telegram_id", telegram_id).execute()


def desbanir_usuario(telegram_id: int):
    supabase.table("users").update({
        "banido": False, "banido_por": None
    }).eq("telegram_id", telegram_id).execute()


def is_banido(telegram_id: int) -> bool:
    user = get_user(telegram_id)
    return bool(user and user.get("banido"))


def listar_usuarios(limit: int = 20, offset: int = 0) -> list:
    return supabase.table("users").select("*") \
        .order("created_at", desc=True) \
        .range(offset, offset + limit - 1) \
        .execute().data


def total_usuarios() -> int:
    res = supabase.table("users").select("id", count="exact").execute()
    return res.count or 0


# ── Estatísticas ──────────────────────────────────────────────────────────────

def stats_gerais() -> dict:
    total_users   = total_usuarios()
    total_gggs    = supabase.table("gggs").select("id", count="exact").execute().count or 0
    gggs_vendidos = supabase.table("gggs").select("id", count="exact").eq("vendido", True).execute().count or 0
    total_ccs     = supabase.table("ccs").select("id", count="exact").execute().count or 0
    ccs_vendidas  = supabase.table("ccs").select("id", count="exact").eq("vendido", True).execute().count or 0
    total_logins  = supabase.table("logins").select("id", count="exact").execute().count or 0
    logins_vend   = supabase.table("logins").select("id", count="exact").eq("vendido", True).execute().count or 0

    # Faturamento total aprovado
    pags = supabase.table("pagamentos").select("valor").eq("status", "approved").execute().data
    faturamento = sum(float(p["valor"]) for p in pags)

    # Saldo total em carteiras dos usuários
    users_saldo = supabase.table("users").select("saldo").execute().data
    saldo_total = sum(float(u["saldo"]) for u in users_saldo)

    return {
        "total_users":   total_users,
        "total_gggs":    total_gggs,
        "gggs_vendidos": gggs_vendidos,
        "gggs_stock":    total_gggs - gggs_vendidos,
        "total_ccs":     total_ccs,
        "ccs_vendidas":  ccs_vendidas,
        "ccs_stock":     total_ccs - ccs_vendidas,
        "total_logins":  total_logins,
        "logins_vend":   logins_vend,
        "logins_stock":  total_logins - logins_vend,
        "faturamento":   faturamento,
        "saldo_total":   saldo_total,
    }


# ── Remoção de produtos ────────────────────────────────────────────────────────

def remover_ggg(ggg_id: int):
    supabase.table("gggs").delete().eq("id", ggg_id).execute()


def remover_cc(cc_id: int):
    supabase.table("ccs").delete().eq("id", cc_id).execute()


def remover_login(login_id: int):
    supabase.table("logins").delete().eq("id", login_id).execute()


def limpar_estoque(tabela: str):
    """Remove todos os itens NÃO vendidos de uma tabela."""
    supabase.table(tabela).delete().eq("vendido", False).execute()


# ── Gift Codes ────────────────────────────────────────────────────────────────

def criar_gift_code(code: str, valor: float, telegram_id: int = 0, criado_por: int | None = None, expires_at: str | None = None) -> dict:
    payload = {
        "code": code.upper().strip(),
        "valor": float(valor),
        "telegram_id": int(telegram_id or 0),
        "used": False,
        "used_by": None,
        "criado_por": criado_por,
        "expires_at": expires_at,
    }
    return supabase.table("gift_codes").insert(payload).execute().data[0]


def get_gift_code(code: str) -> dict | None:
    res = supabase.table("gift_codes").select("*").eq("code", code.upper().strip()).limit(1).execute()
    return res.data[0] if res.data else None


def marcar_gift_code_usado(code: str, used_by: int):
    supabase.table("gift_codes").update({
        "used": True,
        "used_by": used_by,
    }).eq("code", code.upper().strip()).execute()


def listar_gift_codes(limit: int = 20) -> list:
    return supabase.table("gift_codes").select("*").order("created_at", desc=True).limit(limit).execute().data


# Compatibilidade de nome usada por alguns handlers
def is_user_banned(telegram_id: int) -> bool:
    return is_banido(telegram_id)
