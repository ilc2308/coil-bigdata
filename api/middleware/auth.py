"""
middleware/auth.py
Autenticación JWT para la API FastAPI de COIL.

Flujo:
  1. POST /api/v1/auth/token   → recibe user/pass → retorna JWT
  2. Todos los demás endpoints → leen el header Authorization: Bearer <token>

Diseño intencionalmente simple para uso académico:
- Un solo usuario definido en .env (APP_USERNAME / APP_PASSWORD)
- Tokens HS256 con expiración configurable (JWT_EXPIRE_MINUTES)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from api.services.config import Settings, get_settings

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    username: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def _create_access_token(data: dict, settings: Settings) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------

def authenticate_user(username: str, password: str, settings: Settings) -> bool:
    """Verifica credenciales contra las variables de entorno."""
    if username != settings.app_username:
        return False
    # Comparación directa (contraseña en plain text en .env, aceptable para uso académico)
    return password == settings.app_password


def create_token(username: str, settings: Settings) -> Token:
    """Crea y retorna un JWT para el usuario."""
    access_token = _create_access_token({"sub": username}, settings)
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
    )


# ---------------------------------------------------------------------------
# Dependencias de FastAPI
# ---------------------------------------------------------------------------

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    Dependencia que extrae y valida el JWT del header Authorization.
    Inyectar en cualquier endpoint que requiera autenticación.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    return username


# Alias para endpoints que solo necesitan verificar que el usuario está autenticado
CurrentUser = Depends(get_current_user)
