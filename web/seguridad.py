"""Contraseñas (argon2id), tokens opacos y firma de webhooks."""
import hashlib
import hmac
import re
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_ph = PasswordHasher()  # argon2id con parámetros recomendados por la librería
MIN_CLAVE = 8
MAX_INTENTOS = 5
MINUTOS_BLOQUEO = 15


def hashear(clave: str) -> str:
    return _ph.hash(clave)


def verificar(hash_guardado: str, clave: str) -> bool:
    try:
        return _ph.verify(hash_guardado, clave)
    except (VerificationError, InvalidHashError):
        return False


def requiere_rehash(hash_guardado: str) -> bool:
    try:
        return _ph.check_needs_rehash(hash_guardado)
    except InvalidHashError:
        return False


def validar_clave(clave: str) -> str:
    if not isinstance(clave, str) or len(clave) < MIN_CLAVE:
        raise ValueError(f"La contraseña debe tener al menos {MIN_CLAVE} caracteres.")
    if len(clave) > 128:
        raise ValueError("La contraseña es demasiado larga.")
    if not re.search(r"[A-Za-z]", clave) or not re.search(r"\d", clave):
        raise ValueError("La contraseña debe combinar letras y números.")
    return clave


def token() -> str:
    return secrets.token_urlsafe(32)


def huella(valor: str) -> str:
    """Solo se guarda el SHA-256 de los tokens (sesión y recuperación)."""
    return hashlib.sha256(valor.encode()).hexdigest()


def firmar(secreto: str, cuerpo: bytes) -> str:
    return hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()


def firma_valida(secreto: str, cuerpo: bytes, firma: str) -> bool:
    return hmac.compare_digest(firmar(secreto, cuerpo), firma or "")
