"""
PIX via Stripe (PaymentIntent). Confirmação automática por polling do status succeeded.
Documentação: https://docs.stripe.com/payments/pix
"""
from __future__ import annotations

import logging

import stripe

from config import STORE_NAME, STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)


def _stripe_err_msg(exc: BaseException) -> str:
    for attr in ("user_message", "message"):
        m = getattr(exc, attr, None)
        if isinstance(m, str) and m.strip():
            return m.strip()
    body = getattr(exc, "json_body", None) or {}
    err = (body.get("error") or {}) if isinstance(body, dict) else {}
    em = err.get("message")
    if isinstance(em, str) and em.strip():
        return em.strip()
    return str(exc)


def _extrair_codigo_pix_br(d: dict) -> str | None:
    """Lê copia-e-cola EMV do next_action do PaymentIntent (PIX BR)."""
    na = d.get("next_action") or {}
    if isinstance(na, str):
        return None
    pix_block = na.get("pix_display_qr_code") or {}
    if isinstance(pix_block, dict):
        data = pix_block.get("data")
        if isinstance(data, str) and data.strip():
            return data.strip()
    return None


def stripe_disponivel() -> bool:
    k = (STRIPE_SECRET_KEY or "").strip()
    return bool(k and k.startswith(("sk_live_", "sk_test_")) and len(k) > 20)


def _client():
    stripe.api_key = STRIPE_SECRET_KEY.strip()


def criar_pix_stripe(telegram_user_id: int, valor_reais: float) -> tuple[str, str]:
    """
    Cria PaymentIntent PIX e devolve (pi_xxx, string copia e cola / EMV).
    """
    if not stripe_disponivel():
        raise RuntimeError("Stripe não configurado (STRIPE_SECRET_KEY).")

    _client()

    # Stripe usa centavos em BRL; mínimo prático comum 50 centavos
    centavos = max(int(round(valor_reais * 100)), 50)

    try:
        intent = stripe.PaymentIntent.create(
            amount=centavos,
            currency="brl",
            payment_method_types=["pix"],
            description=f"{STORE_NAME} — Telegram {telegram_user_id}",
            metadata={
                "telegram_user_id": str(telegram_user_id),
                "source": "morfel_bot",
            },
            confirm=True,
            payment_method_data={
                "type": "pix",
                "billing_details": {
                    "email": f"tg{telegram_user_id}.pix@telegram.invalid",
                    "name": "Cliente",
                },
            },
            payment_method_options={
                "pix": {
                    "expires_after_seconds": 14400,
                }
            },
        )
    except Exception as e:
        logger.warning("Stripe PaymentIntent.create: %s", e)
        msg = _stripe_err_msg(e)
        raise RuntimeError(msg) from e

    d = intent.to_dict() if hasattr(intent, "to_dict") else dict(intent)
    iid = d.get("id")
    if not iid:
        raise RuntimeError("Stripe não retornou ID do pagamento.")

    br_code = _extrair_codigo_pix_br(d)

    if not br_code and d.get("status") == "requires_action":
        # Algumas contas exigem confirm em segundo passo
        try:
            intent2 = stripe.PaymentIntent.confirm(
                iid,
                payment_method_data={
                    "type": "pix",
                    "billing_details": {
                        "email": f"tg{telegram_user_id}.pix@telegram.invalid",
                        "name": "Cliente",
                    },
                },
            )
            d2 = intent2.to_dict() if hasattr(intent2, "to_dict") else dict(intent2)
            br_code = _extrair_codigo_pix_br(d2)
        except Exception as e:
            msg = _stripe_err_msg(e)
            raise RuntimeError(msg) from e

    if not br_code:
        logger.warning(
            "Stripe PIX sem BR code: status=%s next_action=%s",
            d.get("status"),
            (d.get("next_action") or {}).get("type"),
        )
        raise RuntimeError(
            f"Stripe não devolveu código PIX (status={d.get('status')}). "
            "Confira se PIX está ativo na conta Stripe (Brasil / BRL)."
        )

    return str(iid), str(br_code)


def consultar_status_stripe(payment_intent_id: str) -> str | None:
    """Retorna status do PaymentIntent (succeeded, requires_action, ...) ou None."""
    if not payment_intent_id.startswith("pi_") or not stripe_disponivel():
        return None
    _client()
    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        d = intent.to_dict() if hasattr(intent, "to_dict") else dict(intent)
        return (d.get("status") or "").lower()
    except Exception as e:
        logger.warning("stripe retrieve %s: %s", payment_intent_id, e)
        return None
