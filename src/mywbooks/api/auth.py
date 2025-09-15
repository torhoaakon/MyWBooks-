# src/mywbooks/api/auth.py
import os
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

ISSUER = os.getenv("SUPABASE_ISSUER", "").rstrip("/")
AUDIENCE = os.getenv("SUPABASE_AUDIENCE", "authenticated")
JWKS_URL = os.getenv("SUPABASE_JWKS_URL", "").strip()
JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "").strip()  # for HS256 projects

if not ISSUER:
    raise RuntimeError("Missing SUPABASE_ISSUER environment variable.")

if not (JWKS_URL or JWT_SECRET):
    raise RuntimeError(
        "Provide either SUPABASE_JWKS_URL (RS/ES) or SUPABASE_JWT_SECRET (HS256)."
    )

bearer = HTTPBearer(auto_error=True)


@lru_cache
def _jwks_client() -> PyJWKClient | None:
    return PyJWKClient(JWKS_URL) if JWKS_URL else None


def _decode_jwt(token: str) -> dict:
    """Decode a Supabase JWT, auto-detecting algorithm from header."""
    header = jwt.get_unverified_header(token)
    alg = header.get("alg")

    if alg == "HS256":
        if not JWT_SECRET:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="HS256 token but SUPABASE_JWT_SECRET not set",
            )
        return jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": ["exp", "iat"], "verify_signature": True},
        )

    if alg in {"RS256", "RS512", "ES256", "ES384"}:
        if not JWKS_URL:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"{alg} token but SUPABASE_JWKS_URL not set",
            )
        signing_key = _jwks_client().get_signing_key_from_jwt(token).key  # type: ignore[arg-type]
        return jwt.decode(
            token,
            signing_key,
            algorithms=[alg],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": ["exp", "iat"], "verify_signature": True},
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Unsupported alg: {alg}"
    )


def verify_jwt(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    if cred.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token"
        )

    try:
        return _decode_jwt(cred.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )


CurrentUser = Annotated[dict, Depends(verify_jwt)]
