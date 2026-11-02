"""
routers/auth.py
Endpoint de autenticación — obtención de token JWT.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from api.middleware.auth import Token, authenticate_user, create_token, get_current_user
from api.services.config import Settings, get_settings

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])


@router.post(
    "/token",
    response_model=Token,
    summary="Obtener token de acceso",
    description="Autentica con usuario y contraseña (definidos en .env) y retorna un JWT.",
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    settings: Settings = Depends(get_settings),
):
    if not authenticate_user(form_data.username, form_data.password, settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return create_token(form_data.username, settings)


@router.get(
    "/me",
    summary="Verificar token",
    description="Retorna el nombre de usuario del token activo.",
)
async def me(current_user: str = Depends(get_current_user)):
    return {"username": current_user}
