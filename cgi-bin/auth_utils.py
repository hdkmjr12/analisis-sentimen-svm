import base64
import hashlib
import hmac
import json
import os
import time


def _b64encode(data):
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(data):
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def buat_token(id_admin, berlaku_detik=8 * 60 * 60):
    secret = os.environ.get("APP_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("APP_SECRET belum dikonfigurasi dengan aman.")

    payload = _b64encode(json.dumps({
        "id_admin": int(id_admin),
        "exp": int(time.time()) + berlaku_detik,
    }, separators=(",", ":")).encode("utf-8"))
    signature = _b64encode(hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest())
    return payload + "." + signature


def verifikasi_token(token):
    secret = os.environ.get("APP_SECRET", "")
    if len(secret) < 32 or not token or "." not in token:
        return None

    try:
        payload, signature = token.split(".", 1)
        expected = _b64encode(hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        data = json.loads(_b64decode(payload).decode("utf-8"))
        if int(data.get("exp", 0)) < int(time.time()):
            return None
        return data
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def hash_password(password, iterations=310000):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64encode(salt)}${_b64encode(digest)}"


def verifikasi_password(password, nilai_database):
    if not nilai_database.startswith("pbkdf2_sha256$"):
        return hmac.compare_digest(password, nilai_database)

    try:
        _, iterations, salt, expected = nilai_database.split("$", 3)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), _b64decode(salt), int(iterations)
        )
        return hmac.compare_digest(_b64encode(digest), expected)
    except (ValueError, TypeError):
        return False
