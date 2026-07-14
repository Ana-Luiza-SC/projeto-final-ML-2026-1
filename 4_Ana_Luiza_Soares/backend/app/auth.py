from __future__ import annotations
import base64, hashlib, hmac, json, os
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from app.database import SessionLocal, User, utc_now

ITERATIONS = 310000
REGISTRATION_TRUE_VALUES = {"true", "1", "yes", "on"}


class DuplicateEmailError(ValueError):
    pass


def registration_enabled():
    return (
        os.getenv("ALLOW_REGISTRATION", "")
        .strip()
        .casefold()
        in REGISTRATION_TRUE_VALUES
    )


def _b64(v):
    return base64.urlsafe_b64encode(v).decode().rstrip("=")


def _unb64(v):
    return base64.urlsafe_b64decode(v + "=" * (-len(v) % 4))


def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${_b64(salt)}${_b64(digest)}"


def verify_password(password, encoded):
    try:
        alg, it, salt, expected = encoded.split("$", 3)
        return alg == "pbkdf2_sha256" and hmac.compare_digest(
            hashlib.pbkdf2_hmac("sha256", password.encode(), _unb64(salt), int(it)),
            _unb64(expected),
        )
    except (ValueError, TypeError):
        return False


def _secret():
    value = os.getenv("AUTH_SECRET") or (
        "test-only-secret" if os.getenv("PYTEST_CURRENT_TEST") else ""
    )
    if not value:
        raise RuntimeError("AUTH_SECRET precisa ser configurado.")
    return value.encode()


def create_token(user):
    payload = {
        "sub": user.id,
        "email": user.email,
        "exp": int((utc_now() + timedelta(hours=12)).timestamp()),
    }
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    return (
        body + "." + _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    )


def decode_token(token):
    try:
        body, sig = token.split(".", 1)
        if not hmac.compare_digest(
            hmac.new(_secret(), body.encode(), hashlib.sha256).digest(), _unb64(sig)
        ):
            raise ValueError
        payload = json.loads(_unb64(body))
        if int(payload["exp"]) <= int(datetime.now(timezone.utc).timestamp()):
            raise ValueError
        return payload
    except (ValueError, KeyError, json.JSONDecodeError):
        raise HTTPException(401, "Sessão inválida ou expirada.")


def ensure_user(email, password, user_id=None, update_password=False):
    with SessionLocal() as s:
        user = (
            s.get(User, user_id)
            if user_id
            else s.scalar(select(User).where(User.email == email.strip().casefold()))
        )
        if user is None:
            user = User(
                id=user_id or str(uuid4()),
                email=email.strip().casefold(),
                password_hash=hash_password(password),
            )
            s.add(user)
        elif update_password and not verify_password(password, user.password_hash):
            user.password_hash = hash_password(password)
            user.updated_at = utc_now()
        s.commit()
        s.expunge(user)
        return user


def register_user(display_name, email, password):
    user = User(
        id=str(uuid4()),
        email=email.strip().casefold(),
        display_name=display_name.strip(),
        password_hash=hash_password(password),
        is_active=True,
    )
    with SessionLocal() as s:
        s.add(user)
        try:
            s.commit()
        except IntegrityError as exc:
            s.rollback()
            raise DuplicateEmailError("E-mail já cadastrado.") from exc
        s.expunge(user)
    return user


def bootstrap_test_user():
    email, password = os.getenv("EMAIL_TESTE"), os.getenv("SENHA_TESTE")
    if email and password:
        ensure_user(email, password, update_password=True)


def authenticate(email, password):
    with SessionLocal() as s:
        user = s.scalar(select(User).where(User.email == email.strip().casefold()))
        if user and user.is_active and verify_password(password, user.password_hash):
            s.expunge(user)
            return user
    return None


def get_user(uid):
    with SessionLocal() as s:
        user = s.get(User, uid)
        if user:
            s.expunge(user)
        return user
