from syncer_filesystem_observer import install_filesystem_observer
from file_utils import create_client_ssl_context
import aiohttp
from syncer_workqueue import wait_for_incoming_requests
from syncer_include_installer import async_install_headers
from options import DistBuildOptions
import logging
import asyncio
from typing import Dict


async def async_main(options, loop):
    scheduled_broadcast_tasks: Dict[str, bool] = {}
    
    session = aiohttp.ClientSession()
    sslcontext = create_client_ssl_context()
    await async_install_headers(session, sslcontext, options, scheduled_broadcast_tasks)
    await install_filesystem_observer(session, sslcontext, loop, scheduled_broadcast_tasks, options)
    await wait_for_incoming_requests(options, session)


def main():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    options = DistBuildOptions()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_main(options, loop))



main()