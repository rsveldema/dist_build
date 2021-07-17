"""
Copied over from aiohttp to work around missing feature of running a server inside an existing async context
"""

import asyncio
import socket
from aiohttp.abc import AbstractAccessLogger
import aiohttp
import logging
import ssl
import sys
from aiohttp import web, ClientSession
from aiohttp.web_app import Application
from aiohttp.web_log import AccessLogger
from aiohttp.web_runner import AppRunner, SockSite, TCPSite, UnixSite
from typing import Awaitable, Callable, Dict, Iterable, List, Optional, Type, Union, cast


access_logger = logging.getLogger("aiohttp.access")

async def aio_server(
    app: Union[Application, Awaitable[Application]],
    *,
    port: Optional[int] = None,
    shutdown_timeout: float = 60.0,
    ssl_context: Optional[ssl.SSLContext] = None,
    print: Callable[..., None] = print,
    backlog: int = 128,
    access_log_class: Type[AbstractAccessLogger] = AccessLogger,
    access_log_format: str = AccessLogger.LOG_FORMAT,
    access_log: Optional[logging.Logger] = access_logger,
    handle_signals: bool = True,
    reuse_address: Optional[bool] = None,
    reuse_port: Optional[bool] = None,
) -> None:
    # A internal functio to actually do all dirty job for application running
    if asyncio.iscoroutine(app):
        app = await app  # type: ignore

    app = cast(Application, app)

    runner = AppRunner(
        app,
        handle_signals=handle_signals,
        access_log_class=access_log_class,
        access_log_format=access_log_format,
        access_log=access_log,
    )

    await runner.setup()

    sites = []  # type: List[BaseSite]

    try:
        sites.append(
                TCPSite(
                    runner,
                    port=port,
                    shutdown_timeout=shutdown_timeout,
                    ssl_context=ssl_context,
                    backlog=backlog,
                    reuse_address=reuse_address,
                    reuse_port=reuse_port,
                )
            )


        for site in sites:
            await site.start()

        if print:  # pragma: no branch
            names = sorted(str(s.name) for s in runner.sites)
            print(
                "======== Running on {} ========\n"
                "(Press CTRL+C to quit)".format(", ".join(names))
            )

        # sleep forever by 1 hour intervals,
        # on Windows before Python 3.8 wake up every 1 second to handle
        # Ctrl+C smoothly
        if sys.platform == "win32" and sys.version_info < (3, 8):
            delay = 1
        else:
            delay = 3600

        while True:
            await asyncio.sleep(delay)
    finally:
        await runner.cleanup()