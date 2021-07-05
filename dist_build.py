import json
import ssl
import os
import sys
import logging
import aiohttp
import asyncio
import time
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler

cmdline = sys.argv[1:]

print(cmdline)

fp = open('config.json')
config = json.loads(fp.read())
fp.close()


async def start_compile_job(session, sslcontext, cmdline, syncer_host):
    uri = syncer_host + '/push_compile_job'
    data = aiohttp.FormData()
    data.add_field('cmdline', cmdline)
    data.add_field('env', json.dumps(dict(os.environ)))
    print("start----------------")
    r = await session.post(uri, data = data, ssl=sslcontext)
    print("result = " + str(r))

async def sendData(loop, cmdline, syncer_host):
    session = aiohttp.ClientSession()    
    client_sslcontext = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    #sslcontext.load_verify_locations('certs/server.pem')
    client_sslcontext.check_hostname = False
    client_sslcontext.verify_mode = ssl.CERT_NONE
    #sslcontext.load_cert_chain('certs/server.crt', 'certs/server.key')
    
    await start_compile_job(session, client_sslcontext, cmdline, syncer_host)

loop = asyncio.get_event_loop()
loop.run_until_complete(sendData(loop, cmdline, config['syncer']))
