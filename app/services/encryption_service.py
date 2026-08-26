import base64
import hashlib

from cryptography.fernet import Fernet


class EncryptionService:
    def __init__(self, key: str) -> None:
        if not key:
            msg = "APP_ENCRYPTION_KEY is required"
            raise ValueError(msg)
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")


def mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"
