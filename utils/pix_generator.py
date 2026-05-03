"""
Geração de payload PIX estático (EMV) e QR Code — mesma lógica do projeto italox.
Configure PIX_KEY, PIX_MERCHANT_NAME e PIX_MERCHANT_CITY no .env.
"""
import io

import qrcode

from config import PIX_KEY, PIX_MERCHANT_NAME, PIX_MERCHANT_CITY


def _tlv(id_: str, value: str) -> str:
    return f"{id_}{len(value):02d}{value}"


def _crc16(payload: str) -> str:
    crc = 0xFFFF
    for char in payload:
        crc ^= ord(char) << 8
        for _ in range(8):
            crc = (crc << 1) ^ 0x1021 if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return crc.to_bytes(2, "big").hex().upper()


def build_pix_payload(amount: float) -> str:
    """Monta string EMV para PIX copia-e-cola."""
    name = (PIX_MERCHANT_NAME or "LOJA")[:25]
    city = (PIX_MERCHANT_CITY or "BRASILIA")[:15]
    key = (PIX_KEY or "").strip()
    if not key:
        raise ValueError("PIX_KEY não configurada no .env")

    merchant_account = _tlv(
        "26",
        _tlv("00", "br.gov.bcb.pix") + _tlv("01", key),
    )
    additional = _tlv("62", _tlv("05", "***"))
    base = (
        _tlv("00", "01")
        + merchant_account
        + _tlv("52", "0000")
        + _tlv("53", "986")
        + _tlv("54", f"{amount:.2f}")
        + _tlv("58", "BR")
        + _tlv("59", name)
        + _tlv("60", city)
        + additional
        + "6304"
    )
    return base + _crc16(base)


def generate_qr_image(payload: str) -> io.BytesIO:
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
