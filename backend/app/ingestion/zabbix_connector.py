"""
Zabbix connector — polls Zabbix API for active problems using problem.get.
Maps Zabbix severity integers to internal enum values.
"""
import asyncio
from typing import Any, Optional

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
log = get_logger(__name__)

POLL_INTERVAL_SECONDS = 60


class ZabbixClient:
    """Minimal async Zabbix JSON-RPC client."""

    def __init__(self, api_url: str, user: str, password: str):
        self.api_url = api_url
        self.user = user
        self.password = password
        self._auth_token: Optional[str] = None
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _call(
        self, method: str, params: dict[str, Any], auth: bool = True
    ) -> Any:
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self._next_id(),
        }
        if auth and self._auth_token:
            payload["auth"] = self._auth_token

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(self.api_url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if "error" in data:
            raise RuntimeError(f"Zabbix API error: {data['error']}")
        return data.get("result")

    async def login(self) -> None:
        result = await self._call(
            "user.login",
            {"user": self.user, "password": self.password},
            auth=False,
        )
        self._auth_token = result
        log.info("zabbix_login_ok", user=self.user)

    async def get_active_problems(self) -> list[dict[str, Any]]:
        """Fetch active (unresolved) problems with host info."""
        return await self._call(
            "problem.get",
            {
                "output": "extend",
                "selectHosts": ["host", "hostid"],
                "recent": False,
                "suppressed": False,
                "sortfield": ["eventid"],
                "sortorder": "DESC",
                "limit": 200,
            },
        )

    async def logout(self) -> None:
        if self._auth_token:
            await self._call("user.logout", {})
            self._auth_token = None


async def start_zabbix_poller(
    ingest_callback,
    api_url: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> None:
    """Background polling loop for Zabbix problems."""
    url = api_url or settings.zabbix_api_url
    zabbix_user = user or settings.zabbix_user
    zabbix_pass = password or settings.zabbix_password

    if not all([url, zabbix_user, zabbix_pass]):
        log.warning("zabbix_poller_disabled", reason="credentials not configured")
        return

    log.info("zabbix_poller_starting", url=url)
    client = ZabbixClient(url, zabbix_user, zabbix_pass)
    backoff = 5

    while True:
        try:
            if not client._auth_token:
                await client.login()

            problems = await client.get_active_problems()
            for problem in problems:
                try:
                    await ingest_callback(problem, source="zabbix")
                except Exception as exc:
                    log.error("zabbix_problem_callback_error", error=str(exc))

            backoff = 5
        except Exception as exc:
            log.error("zabbix_poll_error", error=str(exc), backoff=backoff)
            client._auth_token = None
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 120)
            continue

        await asyncio.sleep(POLL_INTERVAL_SECONDS)
