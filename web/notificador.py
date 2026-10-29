"""
Envío de correos y mensajes de WhatsApp.

Sin proveedor configurado, los mensajes se escriben en DATA_DIR/outbox.log
(modo desarrollo). Correo real: DENTAL_SMTP_HOST, DENTAL_SMTP_PORT,
DENTAL_SMTP_USER, DENTAL_SMTP_PASSWORD, DENTAL_SMTP_FROM.
WhatsApp: integrar el proveedor elegido en enviar_whatsapp().
"""
import json
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage

DATA_DIR = os.environ.get("DENTAL_DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))


def _outbox(canal: str, destino: str, asunto: str, cuerpo: str) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "outbox.log"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"en": datetime.now().isoformat(timespec="seconds"), "canal": canal,
                            "para": destino, "asunto": asunto, "cuerpo": cuerpo}, ensure_ascii=False) + "\n")


def enviar_correo(destino: str, asunto: str, cuerpo: str) -> None:
    host = os.environ.get("DENTAL_SMTP_HOST")
    if not host:
        _outbox("correo", destino, asunto, cuerpo)
        return
    msg = EmailMessage()
    msg["From"] = os.environ.get("DENTAL_SMTP_FROM", "Dental Home <no-responder@dentalhome.pe>")
    msg["To"], msg["Subject"] = destino, asunto
    msg.set_content(cuerpo)
    with smtplib.SMTP(host, int(os.environ.get("DENTAL_SMTP_PORT", "587")), timeout=15) as s:
        s.starttls()
        if os.environ.get("DENTAL_SMTP_USER"):
            s.login(os.environ["DENTAL_SMTP_USER"], os.environ.get("DENTAL_SMTP_PASSWORD", ""))
        s.send_message(msg)


def enviar_whatsapp(telefono: str, cuerpo: str) -> None:
    _outbox("whatsapp", telefono, "", cuerpo)
