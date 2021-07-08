from .config import get_build_hosts, get_include_dirs
import ssl
import os
import logging
import aiohttp
import asyncio
from typing import List, Dict
from watchdog.observers import Observer
from aiohttp_session import setup, get_session, session_middleware
from .file_utils import is_header_file, read_binary_content
from .syncer_workqueue import wait_for_incoming_requests

ssl.match_hostname = lambda cert, hostname: True


async def broadcast_file(session: aiohttp.ClientSession, hosts: List[str], path:str, sslcontext):
    content = read_binary_content(path)
    print("file size = " + str(len(content)))
    for host in hosts:
        uri = 'https://' + host + "/install_file"
        data = aiohttp.FormData()
        data.add_field('path', path)
        data.add_field('content', content, content_type='application/octet-stream', content_transfer_encoding="binary") 
        print("start----------------")
        r = await session.post(uri, data = data, ssl=sslcontext)
        print("result = " + str(r))
    scheduled_broadcast_tasks[path] = False


async def install_directory(session: aiohttp.ClientSession, hosts: List[str], dir: str, sslcontext):
    content = os.listdir(dir)
    print("content = " + str(content))
    files: List[str] = []
    for item in content:
        if is_header_file(item):
            print('its a header: ' + item)
            if os.path.isfile(dir + '/' + item):
                files.append(item)
        elif os.path.isdir(dir + '/' + item):
            await install_directory(session, hosts, dir + '/' + item, sslcontext)

    print("all files = " + str(files))
    for filename in files:
        path = dir + '/' + filename
        await broadcast_file(session, hosts, path, sslcontext)


hosts = get_build_hosts()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

scheduled_broadcast_tasks = {}

class FileSystemObserver:
    def __init__(self, session: aiohttp.ClientSession, hosts: List[str], sslcontext, loop):
        self.session = session
        self.hosts = hosts
        self.sslcontext = sslcontext
        self.loop = loop

    def dispatch(self, evt):
        src_path = evt.src_path
        print("got file system evt: " + src_path)

        if not src_path in scheduled_broadcast_tasks or not scheduled_broadcast_tasks[src_path]:
            if is_header_file(src_path):
                scheduled_broadcast_tasks[src_path] = True
                asyncio.run_coroutine_threadsafe(broadcast_file(self.session, hosts, src_path, self.sslcontext), self.loop)
        else:
            print("broadcast of change already scheduled")

async def sendData(loop):
    session = aiohttp.ClientSession()    
    sslcontext = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    #sslcontext.load_verify_locations('certs/server.pem')
    sslcontext.check_hostname = False
    sslcontext.verify_mode = ssl.CERT_NONE
    #sslcontext.load_cert_chain('certs/server.crt', 'certs/server.key')

    event_handler = FileSystemObserver(session, hosts, sslcontext, loop)
    observer = Observer()
    for cdir in get_include_dirs():
        observer.schedule(event_handler, cdir, recursive=True)
    observer.start()
    for cdir in get_include_dirs():
        await install_directory(session, hosts, cdir, sslcontext)

loop = asyncio.get_event_loop()
loop.run_until_complete(sendData(loop))

print("waiting for dir-changes")
#loop.run_forever()

wait_for_incoming_requests()



