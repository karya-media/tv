"""Authentication dependencies for the REST API.

Two independent mechanisms, matching two different trust levels:

- API key (X-API-Key header): required for state-changing endpoints
  (triggering a pipeline run). Compared with secrets.compare_digest to
  avoid leaking the key's value through response-time timing.
- HTTP Basic (optional): protects the read-only dashboard pages, only
  if IPTV_DASHBOARD_USERNAME/PASSWORD are both configured. If unset,
  the dashboard is open - suitable for local/trusted-network use.
"""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPBasic, HTTPBasicCredentials

from iptv_manager.config.settings import Settings, get_settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_basic_auth = HTTPBasic(auto_error=False)


def require_api_key(
    provided: str | None = Depends(_api_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="IPTV_API_KEY is not configured on the server",
        )
    if not provided or not secrets.compare_digest(provided, settings.api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key")


def optional_dashboard_auth(
    credentials: HTTPBasicCredentials | None = Depends(_basic_auth),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.dashboard_username or not settings.dashboard_password:
        return  # dashboard auth not configured -> open access

    valid_user = credentials is not None and secrets.compare_digest(
        credentials.username, settings.dashboard_username
    )
    valid_pass = credentials is not None and secrets.compare_digest(
        credentials.password, settings.dashboard_password
    )
    if not (valid_user and valid_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid dashboard credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
