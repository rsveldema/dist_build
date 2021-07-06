import json
import ssl
import os
from file_utils import is_header_file
import sys
import logging
import aiohttp
import asyncio
import time
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler
from file_utils import is_source_file, read_content, read_config

cmdline = sys.argv[1:]

print(cmdline)


config = read_config()




async def start_compile_job(session, sslcontext, cmdline, syncer_host):
    uri = syncer_host + '/push_compile_job'
    files = {}
    for opt in cmdline:
        if is_source_file(opt):
            files[opt] = read_content(opt)
    data = aiohttp.FormData()
    data.add_field('files', json.dumps(files))
    data.add_field('cmdline', json.dumps(cmdline))
    data.add_field('env', json.dumps(dict(os.environ)))
    print("start----------------")
    r = await session.post(uri, data = data, ssl=sslcontext)
    print("result = " + str(await r.text()))


async def sendDataToSyncer(loop, cmdline, syncer_host):
    session = aiohttp.ClientSession()    
    client_sslcontext = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    #sslcontext.load_verify_locations('certs/server.pem')
    client_sslcontext.check_hostname = False
    client_sslcontext.verify_mode = ssl.CERT_NONE
    #sslcontext.load_cert_chain('certs/server.crt', 'certs/server.key')    
    await start_compile_job(session, client_sslcontext, cmdline, syncer_host)
    await session.close()


loop = asyncio.get_event_loop()
loop.run_until_complete(sendDataToSyncer(loop, cmdline, config['syncer']))
