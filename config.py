import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
BOT_USERNAME = os.getenv("BOT_USERNAME", "").strip()
STORE_NAME = os.getenv("STORE_NAME", "Meu Bot PIX").strip()

MIN_PIX_VALUE = float(os.getenv("MIN_PIX_VALUE", "1.00") or "1.00")

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0").strip()
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "5000") or "5000")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()
SUPABASE_TABLE_USERS = os.getenv("SUPABASE_TABLE_USERS", "users").strip()
SUPABASE_TABLE_PAYMENTS = os.getenv("SUPABASE_TABLE_PAYMENTS", "payments").strip()

MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "").strip()
MP_PUBLIC_KEY = os.getenv("MP_PUBLIC_KEY", "").strip()

ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
COMISSAO_INDICACAO = float(os.getenv("COMISSAO_INDICACAO", "0.10") or "0.10")
PRECO_GGG_UNITARIA = float(os.getenv("PRECO_GGG_UNITARIA", "20.00") or "20.00")
PRECO_GGG_MIX = float(os.getenv("PRECO_GGG_MIX", "60.00") or "60.00")
PRECO_CC_UNITARIA = float(os.getenv("PRECO_CC_UNITARIA", "20.00") or "20.00")
PRECO_CC_MIX = float(os.getenv("PRECO_CC_MIX", "60.00") or "60.00")

PIX_KEY = os.getenv("PIX_KEY", "").strip()
PIX_MERCHANT_NAME = os.getenv("PIX_MERCHANT_NAME", "LOJA").strip()
PIX_MERCHANT_CITY = os.getenv("PIX_MERCHANT_CITY", "BRASILIA").strip()
PIX_USAR_MERCADOPAGO = os.getenv("PIX_USAR_MERCADOPAGO", "true").lower() in ("1", "true", "yes")
PIX_USAR_STRIPE = os.getenv("PIX_USAR_STRIPE", "false").lower() in ("1", "true", "yes")
PIX_NOTIFICAR_DONO_NOVO_PIX = os.getenv("PIX_NOTIFICAR_DONO_NOVO_PIX", "false").lower() in ("1", "true", "yes")
PIX_VALOR_MIN = float(os.getenv("PIX_VALOR_MIN", "1.00") or "1.00")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
PIX_AUTO_APROVAR_DONO = os.getenv("PIX_AUTO_APROVAR_DONO", "false").lower() in ("1", "true", "yes")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN não foi definido no .env")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL e SUPABASE_KEY devem estar definidos no .env")

if not MP_ACCESS_TOKEN:
    raise RuntimeError("MP_ACCESS_TOKEN deve estar definido no .env")
