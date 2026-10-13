"""Authentication seam and short-lived print tokens.

Today the app runs on the internal network for a single team, so `get_current_user` returns a
local user. Every API route already depends on it — adding real login later (company SSO, sessions,
JWT) means changing this one function, not the routes.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

from fastapi import Header, HTTPException, Query


@dataclass
class User:
    id: str
    name: str
    role: str = "editor"


LOCAL_USER = User(id="local", name="فريق أهداف", role="admin")


def get_current_user(authorization: str | None = Header(default=None)) -> User:
    # Placeholder: plug the real identity provider here (validate `authorization`, load the user).
    return LOCAL_USER


# ------------------------------------------------------------------ print tokens
# The PDF exporter opens the print page in a headless browser that has no user session.
# It receives a one-time token scoped to a single proposal and valid for two minutes.
_TOKENS: dict[str, tuple[str, float]] = {}
TOKEN_TTL = 120


def issue_print_token(proposal_id: str) -> str:
    _purge()
    token = secrets.token_urlsafe(24)
    _TOKENS[token] = (proposal_id, time.time() + TOKEN_TTL)
    return token


def check_print_token(proposal_id: str, token: str) -> bool:
    _purge()
    entry = _TOKENS.get(token)
    return bool(entry and entry[0] == proposal_id)


def require_print_token(proposal_id: str, token: str = Query(...)) -> str:
    if not check_print_token(proposal_id, token):
        raise HTTPException(status_code=403, detail="رمز الطباعة غير صالح أو منتهي")
    return token


def _purge() -> None:
    now = time.time()
    for t in [t for t, (_, exp) in _TOKENS.items() if exp < now]:
        _TOKENS.pop(t, None)
