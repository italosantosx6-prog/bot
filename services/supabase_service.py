import logging
from typing import Any, Dict, List, Optional

from supabase import create_client

from config import (
    SUPABASE_KEY,
    SUPABASE_URL,
    SUPABASE_TABLE_PAYMENTS,
    SUPABASE_TABLE_USERS,
)

logger = logging.getLogger(__name__)


class SupabaseService:
    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL e SUPABASE_KEY são obrigatórios")

        self.client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.users_table = SUPABASE_TABLE_USERS
        self.payments_table = SUPABASE_TABLE_PAYMENTS

    def get_or_create_user(self, telegram_id: int, username: Optional[str] = None) -> Dict[str, Any]:
        response = (
            self.client.table(self.users_table)
            .select("*")
            .eq("telegram_id", telegram_id)
            .limit(1)
            .execute()
        )
        user = response.data[0] if response.data else None
        if user:
            return user

        new_user = {
            "telegram_id": telegram_id,
            "username": username or "",
            "saldo": 0,
        }
        created = self.client.table(self.users_table).insert(new_user).execute()
        if not created.data:
            raise RuntimeError("Falha ao criar usuário no Supabase")
        return created.data[0]

    def create_payment(
        self,
        telegram_id: int,
        amount: float,
        external_reference: str,
        payment_id: str,
        qr_code: str,
        pix_copy_text: str,
        status: str = "pending",
    ) -> Dict[str, Any]:
        payload = {
            "telegram_id": telegram_id,
            "amount": float(round(amount, 2)),
            "external_reference": external_reference,
            "payment_id": payment_id,
            "status": status,
            "qr_code": qr_code,
            "pix_copy_text": pix_copy_text,
        }
        response = self.client.table(self.payments_table).insert(payload).execute()
        if not response.data:
            logger.error("Falha ao inserir pagamento no Supabase: %s", response.error)
            raise RuntimeError("Falha ao registrar pagamento")
        return response.data[0]

    def find_pending_payment(self, telegram_id: int, amount: float) -> Optional[Dict[str, Any]]:
        response = (
            self.client.table(self.payments_table)
            .select("*")
            .eq("telegram_id", telegram_id)
            .eq("amount", float(round(amount, 2)))
            .eq("status", "pending")
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    def get_payment_by_id(self, payment_id: str) -> Optional[Dict[str, Any]]:
        response = (
            self.client.table(self.payments_table)
            .select("*")
            .eq("payment_id", payment_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    def update_payment_status(
        self,
        payment_id: str,
        status: str,
        approved_at: Optional[str] = None,
        raw_response: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        payload = {"status": status}
        if approved_at:
            payload["approved_at"] = approved_at
        if raw_response is not None:
            payload["raw_response"] = raw_response

        response = (
            self.client.table(self.payments_table)
            .update(payload)
            .eq("payment_id", payment_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def add_balance(self, telegram_id: int, amount: float) -> None:
        user = self.get_or_create_user(telegram_id)
        new_balance = float(user.get("saldo", 0) or 0) + float(round(amount, 2))
        response = (
            self.client.table(self.users_table)
            .update({"saldo": new_balance})
            .eq("telegram_id", telegram_id)
            .execute()
        )
        if not response.data:
            raise RuntimeError("Falha ao atualizar saldo do usuário")

    def get_user_balance(self, telegram_id: int) -> float:
        user = self.get_or_create_user(telegram_id)
        return float(user.get("saldo", 0) or 0)
