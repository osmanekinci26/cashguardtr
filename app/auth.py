import os
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import hashlib
import hmac

# MVP: basit şifre hash (bcrypt de yaparız ama hızlı olsun diye)
# İstersen sonra bcrypt'e geçiririz.

SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME_SECRET_KEY")
SER = URLSafeTimedSerializer(SECRET_KEY, salt="cashguard-admin")

SESSION_MAX_AGE = 60 * 60 * 12  # 12 saat


def hash_password(password: str) -> str:
    # SHA256 + secret pepper (MVP)
    pepper = os.getenv("PASSWORD_PEPPER", "CHANGE_ME_PEPPER")
    return hashlib.sha256((pepper + password).encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash)


def make_session(email: str) -> str:
    return SER.dumps({"email": email})


def read_session(token: str):
    try:
        data = SER.loads(token, max_age=SESSION_MAX_AGE)
        return data
    except (BadSignature, SignatureExpired):
        return None
