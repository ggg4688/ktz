from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import AppSettings
from app.models import PublicUser, RoleName, TokenResponse
from app.repository import SnapshotRepository

ROLE_LEVELS: dict[RoleName, int] = {
    "viewer": 1,
    "operator": 2,
    "admin": 3,
}
DEFAULT_PASSWORD_ITERATIONS = 120_000


@dataclass(slots=True)
class StoredUserRecord:
    username: str
    full_name: str
    role: RoleName
    salt: bytes
    password_hash: str
    iterations: int
    disabled: bool


class AuthService:
    def __init__(self, settings: AppSettings, repository: SnapshotRepository) -> None:
        self._secret = settings.jwt_secret.encode("utf-8")
        self._issuer = settings.jwt_issuer
        self._ttl_minutes = settings.jwt_access_token_ttl_minutes
        self._repository = repository

    def authenticate_user(self, username: str, password: str) -> PublicUser | None:
        user = self._get_user_record(username)
        if user is None or user.disabled:
            return None
        if not verify_password(password, user):
            return None
        return self._to_public_user(user)

    def issue_token(self, user: PublicUser) -> TokenResponse:
        issued_at = utc_now()
        expires_at = issued_at + timedelta(minutes=self._ttl_minutes)
        payload = {
            "sub": user.username,
            "role": user.role,
            "full_name": user.full_name,
            "iss": self._issuer,
            "iat": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        token = _encode_jwt(payload, self._secret)
        return TokenResponse(
            access_token=token,
            expires_at=expires_at,
            user=user,
        )

    def get_user_from_token(self, token: str) -> PublicUser:
        payload = _decode_jwt(token, self._secret, self._issuer)
        username = payload.get("sub")
        if not isinstance(username, str) or not username:
            raise ValueError("Token payload is missing subject")

        user = self._get_user_record(username)
        if user is None or user.disabled:
            raise ValueError("User is not allowed to access the service")

        return self._to_public_user(user)

    def list_users(self) -> list[PublicUser]:
        return [
            self._to_public_user(self._raw_to_stored_user(raw_user))
            for raw_user in self._repository.list_users()
        ]

    def create_user(
        self,
        username: str,
        password: str,
        role: RoleName,
        full_name: str | None = None,
    ) -> PublicUser:
        salt, password_hash, iterations = build_password_record(password)
        raw_user = self._repository.create_user(
            username=username,
            full_name=full_name or username,
            role=role,
            salt=salt.hex(),
            password_hash=password_hash,
            iterations=iterations,
            disabled=False,
        )
        return self._to_public_user(self._raw_to_stored_user(raw_user))

    @staticmethod
    def role_allows(current_role: RoleName, required_role: RoleName) -> bool:
        return ROLE_LEVELS[current_role] >= ROLE_LEVELS[required_role]

    @staticmethod
    def _to_public_user(user: StoredUserRecord) -> PublicUser:
        return PublicUser(
            username=user.username,
            full_name=user.full_name,
            role=user.role,
        )

    def _get_user_record(self, username: str) -> StoredUserRecord | None:
        raw_user = self._repository.get_user(username)
        if raw_user is None:
            return None
        return self._raw_to_stored_user(raw_user)

    @staticmethod
    def _raw_to_stored_user(raw_user: dict[str, Any]) -> StoredUserRecord:
        role = raw_user["role"]
        if role not in ROLE_LEVELS:
            raise ValueError(f"Unsupported role: {role}")

        return StoredUserRecord(
            username=raw_user["username"],
            full_name=raw_user["full_name"],
            role=role,
            salt=bytes.fromhex(raw_user["salt"]),
            password_hash=raw_user["password_hash"],
            iterations=int(raw_user["iterations"]),
            disabled=bool(raw_user["disabled"]),
        )


def hash_password(password: str, salt: bytes, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()


def build_password_record(password: str, iterations: int = DEFAULT_PASSWORD_ITERATIONS) -> tuple[bytes, str, int]:
    salt = secrets.token_bytes(16)
    password_hash = hash_password(password, salt, iterations)
    return salt, password_hash, iterations


def verify_password(password: str, user: StoredUserRecord) -> bool:
    expected = hash_password(password, user.salt, user.iterations)
    return hmac.compare_digest(expected, user.password_hash)


def _encode_jwt(payload: dict[str, Any], secret: bytes) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_segment = _b64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    payload_segment = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    signature = hmac.new(secret, signing_input, hashlib.sha256).digest()
    return f"{header_segment}.{payload_segment}.{_b64url_encode(signature)}"


def _decode_jwt(token: str, secret: bytes, expected_issuer: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Malformed bearer token")

    header_segment, payload_segment, signature_segment = parts
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    actual_signature = _b64url_decode(signature_segment)
    expected_signature = hmac.new(secret, signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(actual_signature, expected_signature):
        raise ValueError("Invalid bearer token signature")

    header = json.loads(_b64url_decode(header_segment))
    if header.get("alg") != "HS256":
        raise ValueError("Unsupported token algorithm")

    payload = json.loads(_b64url_decode(payload_segment))
    if payload.get("iss") != expected_issuer:
        raise ValueError("Invalid token issuer")

    expires_at = payload.get("exp")
    if not isinstance(expires_at, int | float):
        raise ValueError("Token payload is missing expiration")

    if datetime.fromtimestamp(expires_at, tz=timezone.utc) <= utc_now():
        raise ValueError("Bearer token expired")

    return payload


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
