"""
Cobrança PIX via API Mercado Pago — permite confirmação automática ao consultar status.
Requer MP_ACCESS_TOKEN válido e conta com PIX por API liberado.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import mercadopago

from config import BOT_USERNAME, MP_ACCESS_TOKEN, STORE_NAME

logger = logging.getLogger(__name__)

PIX_EXPIRATION_MINUTES = 30


def mp_disponivel() -> bool:
    t = (MP_ACCESS_TOKEN or "").strip()
    return bool(t and not t.startswith("SEU_") and len(t) > 10)


def _sdk():
    return mercadopago.SDK(MP_ACCESS_TOKEN.strip())


def criar_cobranca_pix_mp(telegram_user_id: int, valor: float) -> tuple[str, str]:
    """
    Cria pagamento PIX no Mercado Pago.
    Retorna (payment_id como string, qr_code copia e cola).
    Levanta RuntimeError se a API falhar.
    """
    if not mp_disponivel():
        raise RuntimeError("Mercado Pago não configurado.")

    expiracao = (
        datetime.now(timezone.utc) + timedelta(minutes=PIX_EXPIRATION_MINUTES)
    ).isoformat()

    payment_data = {
        "transaction_amount": float(valor),
        "description": f"Recarga {STORE_NAME} - ID {telegram_user_id}",
        "payment_method_id": "pix",
        "date_of_expiration": expiracao,
        "payer": {
            "email": f"{telegram_user_id}@{BOT_USERNAME}.bot",
            "first_name": "Cliente",
            "last_name": str(telegram_user_id),
        },
    }

    response = _sdk().payment().create(payment_data)
    if not isinstance(response, dict):
        raise RuntimeError("Resposta inválida do Mercado Pago.")

    status_http = response.get("status")
    body = response.get("response")
    if not isinstance(body, dict):
        raise RuntimeError(f"Resposta inválida do Mercado Pago (HTTP {status_http}).")

    if status_http not in (200, 201):
        parts = []
        for key in ("message", "error", "status_detail"):
            v = body.get(key)
            if v:
                parts.append(str(v))
        causes = body.get("cause")
        if causes is not None:
            parts.append(str(causes)[:400])
        detail = " ".join(parts).strip() or str(body)[:500]
        raise RuntimeError(f"Mercado Pago HTTP {status_http}: {detail}")

    payment_id = body.get("id")
    tx_data = body.get("point_of_interaction", {}).get("transaction_data", {})
    qr_code = tx_data.get("qr_code")

    if not payment_id:
        msg = body.get("message") or body.get("status_detail") or "sem id"
        raise RuntimeError(f"Mercado Pago não retornou ID: {msg}")
    if not qr_code:
        raise RuntimeError("Mercado Pago não retornou código PIX.")

    return str(payment_id), str(qr_code)


def consultar_status_mp(payment_id: str) -> str | None:
    """Retorna status da API (approved, pending, cancelled, ...) ou None em erro."""
    try:
        r = _sdk().payment().get(payment_id)
        body = r.get("response")
        if isinstance(body, dict):
            return (body.get("status") or "").lower()
    except Exception as e:
        logger.warning("consultar_status_mp %s: %s", payment_id, e)
    return None
