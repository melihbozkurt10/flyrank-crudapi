"""Supabase auth: signup, login, logout, and a reusable FastAPI dependency."""

import os

from dotenv import load_dotenv
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from supabase import Client, create_client

load_dotenv()

bearer = HTTPBearer(auto_error=False)


class AuthError(Exception):
    def __init__(self, status_code: int, error: str):
        self.status_code = status_code
        self.error = error


class AuthIn(BaseModel):
    email: str
    password: str


def connect_supabase() -> Client | None:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    if not url or not key or "your-project" in url or key == "your_anon_key":
        return None
    return create_client(url, key)


supabase = connect_supabase()
if supabase is not None:
    print("Server running and connected to Supabase")
else:
    print("Server running (Supabase not configured - set SUPABASE_URL and SUPABASE_KEY)")


def require_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    """FastAPI dependency: require a valid Bearer JWT. Raises AuthError otherwise."""
    if creds is None or creds.scheme.lower() != "bearer" or not creds.credentials:
        raise AuthError(401, "Access token required")
    if supabase is None:
        raise AuthError(401, "Invalid or expired token")
    try:
        result = supabase.auth.get_user(creds.credentials)
    except Exception:
        raise AuthError(401, "Invalid or expired token") from None
    user = getattr(result, "user", None)
    if user is None:
        raise AuthError(401, "Invalid or expired token")
    return {
        "id": user.id,
        "email": user.email,
        "created_at": str(user.created_at) if user.created_at else None,
        "access_token": creds.credentials,
    }


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "created_at": user["created_at"],
    }


def sign_out_token(access_token: str) -> None:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    authed = create_client(url, key)
    authed.auth.set_session(access_token, access_token)
    authed.auth.sign_out()
