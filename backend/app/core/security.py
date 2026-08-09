from cryptography.fernet import Fernet
from ..config import settings

class SessionEncryptor:
    def __init__(self):
        # Берем ключ из объекта settings, который загружает Pydantic
        key = settings.SESSION_ENCRYPTION_KEY
        if not key:
            raise ValueError("SESSION_ENCRYPTION_KEY must be set in .env")
        self.cipher = Fernet(key.encode())

    def encrypt(self, data: str) -> str:
        return self.cipher.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        return self.cipher.decrypt(encrypted_data.encode()).decode()

encryptor = SessionEncryptor()