import logging
from typing import Dict, Optional

import mercadopago

from config import MP_ACCESS_TOKEN

logger = logging.getLogger(__name__)


class MercadoPagoService:
    def __init__(self, access_token: str = MP_ACCESS_TOKEN):
        self.access_token = access_token.strip()
        if not self.access_token:
            raise RuntimeError("MP_ACCESS_TOKEN não encontrado em config.py ou .env")
        self.client = mercadopago.SDK(self.access_token)

    def create_pix_payment(
        self,
        amount: float,
        external_reference: str,
        description: str = "Pagamento via PIX",
    ) -> Dict:
        payload = {
            "transaction_amount": float(round(amount, 2)),
            "description": description,
            "payment_method_id": "pix",
            "external_reference": external_reference,
            "payer": {"email": "no-reply@seubot.com"},
        }

        response = self.client.payment().create(payload)
        status = response.get("status")
        if status not in (200, 201):
            error_body = response.get("response")
            logger.error("Erro ao criar pagamento Mercado Pago: %s", error_body)
            raise RuntimeError("Falha ao criar pagamento Mercado Pago")

        data = response.get("response") or {}
        transaction_data = (
            data.get("point_of_interaction", {})
            .get("transaction_data", {})
        )
        qr_data = transaction_data.get("qr_code")
        pix_copy_text = qr_data

        if not qr_data:
            logger.error("Resposta inesperada do Mercado Pago: %s", data)
            raise RuntimeError("QR Code não foi retornado pelo Mercado Pago")

        return {
            "payment_id": str(data.get("id")),
            "status": data.get("status"),
            "amount": float(data.get("transaction_amount", amount)),
            "external_reference": data.get("external_reference", external_reference),
            "qr_code": qr_data,
            "pix_copy_text": pix_copy_text,
            "expiration_date": data.get("date_of_expiration"),
            "raw_response": data,
        }

    def get_payment(self, payment_id: str) -> Optional[Dict]:
        response = self.client.payment().get(payment_id)
        if response.get("status") not in (200, 201):
            logger.error("Falha ao buscar pagamento Mercado Pago: %s", response)
            return None
        return response.get("response")
