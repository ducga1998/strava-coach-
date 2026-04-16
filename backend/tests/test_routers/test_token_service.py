from app.services.token_service import TokenService

TEST_KEY = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="


def test_encrypt_decrypt_roundtrip() -> None:
    service = TokenService(TEST_KEY)
    plaintext = "acc_token_abc123"
    ciphertext = service.encrypt(plaintext)
    assert ciphertext != plaintext
    assert service.decrypt(ciphertext) == plaintext


def test_different_encryptions_same_input() -> None:
    service = TokenService(TEST_KEY)
    first = service.encrypt("same")
    second = service.encrypt("same")
    assert first != second
    assert service.decrypt(first) == service.decrypt(second) == "same"
