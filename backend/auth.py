import threading
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.auth_config import (
    SECRET_KEY, ALGORITHM, TOKEN_EXPIRE_HOURS, ALLOW_MULTIPLE_SESSIONS,
)
from bot.logging_config import get_security_logger

sec_log = get_security_logger()
security = HTTPBearer()

# ── Single-session enforcement ──────────────────────────────────
_session_lock = threading.Lock()
_active_token_version: int = 0  # bumped on each login when single-session


def _next_token_version() -> int:
    global _active_token_version
    with _session_lock:
        _active_token_version += 1
        return _active_token_version


def _current_token_version() -> int:
    with _session_lock:
        return _active_token_version


# ── Token helpers ───────────────────────────────────────────────

def create_token(username: str) -> str:
    version = _next_token_version()
    payload = {
        "sub": username,
        "ver": version,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    if not ALLOW_MULTIPLE_SESSIONS:
        sec_log.info(
            "action=session_created | user=%s | version=%d | note=previous sessions invalidated",
            username, version,
        )
    return token


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload["sub"]

        # Single-session check
        if not ALLOW_MULTIPLE_SESSIONS:
            token_ver = payload.get("ver", 0)
            if token_ver != _current_token_version():
                sec_log.warning(
                    "action=session_invalidated | user=%s | token_ver=%d | active_ver=%d",
                    username, token_ver, _current_token_version(),
                )
                raise HTTPException(
                    status_code=401,
                    detail="Session expired. Please login again.",
                )

        return username

    except JWTError:
        sec_log.warning("action=invalid_jwt | token=%s…", token[:16])
        raise HTTPException(status_code=401, detail="Invalid token")
