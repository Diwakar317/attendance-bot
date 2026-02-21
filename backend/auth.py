from jose import jwt
from datetime import datetime, timedelta
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.auth_config import SECRET_KEY, ALGORITHM

security = HTTPBearer()


def create_token(username: str):

    payload = {
        "sub": username,
        "exp": datetime.utcnow() + timedelta(hours=12)
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        return payload["sub"]

    except:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )
