from flask import Flask, request, jsonify
import os
import logging
from telegram import Bot

from database.db import (
    get_pagamento,
    aprovar_pagamento_se_pendente,
    update_saldo,
    pagar_comissao,
)

from config import BOT_TOKEN, MP_WEBHOOK_SECRET, STRIPE_WEBHOOK_SECRET

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
bot = Bot(BOT_TOKEN)


def _process_and_credit(payment_id: str):
    """Marca pagamento como aprovado (se estiver pending) e credita o usuário.
    Retorna tuple (ok: bool, msg: str)
    """
    pag = get_pagamento(payment_id)
    if not pag:
        logger.info("webhook: pagamento nao encontrado %s", payment_id)
        return False, "payment not found"

    if (pag.get("status") or "").lower() != "pending":
        logger.info("webhook: pagamento ja processado %s status=%s", payment_id, pag.get("status"))
        return False, "already processed"

    # Tenta marcar como aprovado (idempotente)
    ok = aprovar_pagamento_se_pendente(payment_id)
    if not ok:
        logger.info("webhook: aprovar_pagamento_se_pendente retornou False %s", payment_id)
        return False, "not updated"

    try:
        # recarrega pagamento
        pag2 = get_pagamento(payment_id)
        telegram_id = int(pag2.get("telegram_id"))
        valor = float(pag2.get("valor"))
        # credita saldo e comissao
        update_saldo(telegram_id, valor)
        pagar_comissao(telegram_id, valor)
        # notifica usuario
        bot.send_message(
            telegram_id,
            f"✅ Pagamento confirmado!\n\n💰 Valor creditado: R$ {valor:.2f}\n\nVolte ao menu para usar seus créditos.",
        )
        return True, "credited"
    except Exception as e:
        logger.exception("erro ao creditar pagamento %s: %s", payment_id, e)
        return False, "error"


@app.route("/webhook/mp", methods=["POST"])
def webhook_mp():
    # validação simples por header (opcional)
    secret = MP_WEBHOOK_SECRET or os.getenv("MP_WEBHOOK_SECRET")
    if secret:
        header_sig = request.headers.get("X-MP-Hook-Signature") or request.headers.get("x-hook-signature")
        if not header_sig or header_sig != secret:
            logger.warning("webhook_mp: assinatura inválida")
            return jsonify({"ok": False, "reason": "invalid signature"}), 403

    payload = request.get_json(force=True)
    # Mercado Pago estrutura varia; tentamos extrair um payment id
    payment_id = None
    try:
        if isinstance(payload, dict):
            # exemplo: {"type":"payment","data":{"id":1234567890}}
            data = payload.get("data") or payload.get("resource")
            if isinstance(data, dict) and data.get("id"):
                payment_id = str(data.get("id"))
            # ou pode vir como {"id": "..."}
            if not payment_id and payload.get("id"):
                payment_id = str(payload.get("id"))
    except Exception:
        logger.exception("webhook_mp: erro ao parsear payload")

    if not payment_id:
        logger.info("webhook_mp: payment_id não encontrado no payload")
        return jsonify({"ok": False, "reason": "no payment id"}), 400

    ok, msg = _process_and_credit(payment_id)
    status_code = 200 if ok else 202
    return jsonify({"ok": ok, "msg": msg}), status_code


@app.route("/webhook/stripe", methods=["POST"])
def webhook_stripe():
    secret = STRIPE_WEBHOOK_SECRET or os.getenv("STRIPE_WEBHOOK_SECRET")
    # validação simples: comparar header
    if secret:
        header_sig = request.headers.get("Stripe-Signature")
        if not header_sig or secret not in header_sig:
            logger.warning("webhook_stripe: assinatura inválida")
            return jsonify({"ok": False, "reason": "invalid signature"}), 403

    payload = request.get_json(force=True)
    event_type = payload.get("type")
    payment_id = None
    try:
        # Para payment_intent.succeeded -> payload['data']['object']['id'] é o PaymentIntent
        if event_type == "payment_intent.succeeded":
            obj = payload.get("data", {}).get("object", {})
            payment_id = obj.get("id")
        # Outros formatos podem enviar charges, etc.
        if not payment_id:
            # tenta pegar id direto
            data = payload.get("data")
            if isinstance(data, dict):
                obj = data.get("object") or {}
                if obj and obj.get("id"):
                    payment_id = obj.get("id")
    except Exception:
        logger.exception("webhook_stripe: erro ao parsear payload")

    if not payment_id:
        logger.info("webhook_stripe: payment_id não encontrado")
        return jsonify({"ok": False, "reason": "no payment id"}), 400

    ok, msg = _process_and_credit(payment_id)
    status_code = 200 if ok else 202
    return jsonify({"ok": ok, "msg": msg}), status_code


if __name__ == "__main__":
    port = int(os.getenv("WEBHOOK_PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
