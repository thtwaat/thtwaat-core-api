"""Rate-limit helpers compatible with nested FastAPI routers.

Upstream ``fastapi_limiter.depends.RateLimiter`` indexes ``app.routes`` by
``.path``, which crashes on Starlette ``_IncludedRouter`` mounts
(``AttributeError: '_IncludedRouter' object has no attribute 'path'``).
This wrapper keys limits by request path + method instead.
"""

from __future__ import annotations

from fastapi import Depends, Request, Response
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from redis.exceptions import NoScriptError


class PathRateLimiter(RateLimiter):
    """Same Redis Lua limiter as fastapi-limiter, without route-index scanning."""

    async def __call__(self, request: Request, response: Response):  # type: ignore[override]
        if not FastAPILimiter.redis:
            raise Exception("You must call FastAPILimiter.init in startup event of fastapi!")

        identifier = self.identifier or FastAPILimiter.identifier
        callback = self.callback or FastAPILimiter.http_callback
        rate_key = await identifier(request)
        path = request.scope.get("path", "")
        method = request.scope.get("method", "")
        key = f"{FastAPILimiter.prefix}:{rate_key}:{method}:{path}:{self.times}:{self.milliseconds}"

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
