# Core authentication utilities

from fastapi import Request, HTTPException, status
from app.core.config import settings

async def verify_mcp_api_token(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated: Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = auth_header.split()
    if parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated: Authorization header must start with Bearer",
            headers={"WWW-Authenticate": "Bearer"},
        )
    elif len(parts) == 1:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated: Token not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    elif len(parts) > 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated: Authorization header must be Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = parts[1]
    if token != settings.MCP_API_TOKEN_SECRET:
        # print(f"Token received: {token}") # For debugging, remove in prod
        # print(f"Expected token: {settings.MCP_API_TOKEN_SECRET}") # For debugging
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials: Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True

