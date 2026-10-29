"""
Pasarela de pago.

PASARELA=simulada (por defecto) abre una página de pago de prueba dentro de la app que
envía un webhook firmado, igual que lo haría una pasarela real. Para cobrar de verdad,
implementa crear_cobro() con el SDK elegido (Culqi, Niubiz, Mercado Pago, Stripe…) y
configura su webhook hacia POST /api/webhooks/<pasarela> con la firma HMAC-SHA256 del
cuerpo en la cabecera X-Firma (o adapta verificar_firma al esquema del proveedor).
"""
import os

from web.seguridad import firma_valida

PASARELA = os.environ.get("DENTAL_PASARELA", "simulada")
SIMULADA_ACTIVA = PASARELA == "simulada" and os.environ.get("DENTAL_ENV") != "production"


def secreto_webhook() -> str:
    from flask import current_app
    return os.environ.get("DENTAL_WEBHOOK_SECRET") or current_app.secret_key + ":webhook"


def crear_cobro(referencia: str, monto: float, plan: str, clinica: str) -> str:
    """Devuelve la URL a la que se envía al administrador para pagar."""
    if PASARELA == "simulada":
        if not SIMULADA_ACTIVA:
            raise ValueError("La pasarela de prueba está desactivada en producción.")
        return f"#/pago/{referencia}"
    raise ValueError(f"La pasarela {PASARELA} aún no está integrada.")


def verificar_firma(cuerpo: bytes, firma: str) -> bool:
    return firma_valida(secreto_webhook(), cuerpo, firma)
