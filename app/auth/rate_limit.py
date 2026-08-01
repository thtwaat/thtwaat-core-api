"""Path-keyed rate limits for nested FastAPI routers.

Upstream ``fastapi_limiter.depends.RateLimiter`` indexes ``app.routes`` by
``.path``, which crashes on Starlette ``_IncludedRouter`` mounts
(``AttributeError: '_IncludedRouter' object has no attribute 'path'``).

This module does not import or subclass that dependency. It uses only
``FastAPILimiter`` Redis Lua helpers and keys limits by request path + method.
"""

from __future__ import annotations

from typing import Callable, Optional

from fastapi import Depends, Request, Response
from fastapi_limiter import FastAPILimiter
from redis.exceptions import NoScriptError


class PathRateLimiter:
    """Redis Lua rate limiter keyed by client id + HTTP method + path."""

    def __init__(
        self,
        times: int = 1,
        milliseconds: int = 0,
        seconds: int = 0,
        minutes: int = 0,
        hours: int = 0,
        identifier: Optional[Callable] = None,
        callback: Optional[Callable] = None,
    ):
        self.times = times
        self.milliseconds = (
            milliseconds + 1000 * seconds + 60000 * minutes + 3600000 * hours
        )
        self.identifier = identifier
        self.callback = callback

    async def _check(self, key: str):
        redis = FastAPILimiter.redis
        return await redis.evalsha(
            FastAPILimiter.lua_sha, 1, key, str(self.times), str(self.milliseconds)
        )

    async def __call__(self, request: Request, response: Response):
        if not FastAPILimiter.redis:
            raise Exception(
                "You must call FastAPILimiter.init in startup event of fastapi!"
            )

        identifier = self.identifier or FastAPILimiter.identifier
        callback = self.callback or FastAPILimiter.http_callback
        rate_key = await identifier(request)
        path = request.scope.get("path", "")
        method = request.scope.get("method", "")
        key = (
            f"{FastAPILimiter.prefix}:{rate_key}:{method}:{path}:"
            f"{self.times}:{self.milliseconds}"
        )

        try:
            pexpire = await self._check(key)
        except NoScriptError:
            FastAPILimiter.lua_sha = await FastAPILimiter.redis.script_load(
                FastAPILimiter.lua_script
            )
            pexpire = await self._check(key)

        if pexpire != 0:
            return await callback(request, response, pexpire)


def auth_rate_limit(times: int, seconds: int) -> list:
    """FastAPI route ``dependencies=[...]`` helper."""
    return [Depends(PathRateLimiter(times=times, seconds=seconds))]
