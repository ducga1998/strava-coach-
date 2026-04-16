import base64
import binascii
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings


class TokenServiceError(ValueError):
    pass


@dataclass(frozen=True)
class TokenService:
    key_base64: str

    def encrypt(self, plaintext: str) -> str:
        key = self._decode_key()
        nonce = os.urandom(12)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ciphertext).decode("utf-8")

    def decrypt(self, token: str) -> str:
        raw = self._decode_payload(token)
        nonce = raw[:12]
        ciphertext = raw[12:]
        plaintext = AESGCM(self._decode_key()).decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")

    def _decode_key(self) -> bytes:
        try:
            key = base64.b64decode(self.key_base64, validate=True)
        except binascii.Error as error:
            raise TokenServiceError("encryption key must be base64") from error
        if len(key) != 32:
            raise TokenServiceError("encryption key must decode to 32 bytes")
        return key

    @staticmethod
    def _decode_payload(token: str) -> bytes:
        try:
            raw = base64.b64decode(token.encode("utf-8"), validate=True)
        except binascii.Error as error:
            raise TokenServiceError("ciphertext must be base64") from error
        if len(raw) <= 12:
            raise TokenServiceError("ciphertext payload is too short")
        return raw


def get_token_service() -> TokenService:
    return TokenService(settings.encryption_key)


def encrypt(plaintext: str) -> str:
    return get_token_service().encrypt(plaintext)


def decrypt(token: str) -> str:
    return get_token_service().decrypt(token)
