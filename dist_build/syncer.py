from aiohttp.client import ClientSession
from aiohttp.client_exceptions import SSLContext
from dist_build.serializer import Serializer
from dist_build.options import DistBuildOptions
from re import fullmatch
from .config import get_build_hosts, get_include_dirs
import ssl
import os
import logging
import aiohttp
import asyncio
from typing import List, Dict, Tuple
from watchdog.observers import Observer
from aiohttp_session import setup, get_session, session_middleware
from .file_utils import is_header_file, read_binary_content
from .syncer_workqueue import wait_for_incoming_requests
from tqdm import tqdm


ssl.match_hostname = lambda cert, hostname: True

MAX_UPLOAD_SIZE = (1024 * 1024 * 2)
serializer = Serializer()


async def do_broadcast_of_serialized_data(session: aiohttp.ClientSession, serializer:Serializer, hosts, sslcontext: ssl.SSLContext):
    #print("file size = " + str(len(content)))
    for host in hosts:
        uri = 'https://' + host + "/install_file"
        data = aiohttp.FormData()
        data.add_field('content', serializer.payload(), content_type='application/octet-stream', content_transfer_encoding="binary") 
        #print("start----------------")
        async with session.post(uri, data = data, ssl=sslcontext) as post_response:
            post_result = await post_response.read()
            post_result = post_result.decode('utf-8')
            if post_result != "ok":
                print(f"post result = {post_result} when trying to send a header file chunk to daemon {host}")
                os.exit(1)

        # print("result = " + str(r))
    serializer.clear()



async def broadcast_files(session: aiohttp.ClientSession, hosts: List[str], dir:str, files:List[str], sslcontext: ssl.SSLContext,
                         scheduled_broadcast_tasks: Dict[str, bool], options: DistBuildOptions, serializer: Serializer):   
    if len(hosts) == 0:
        print("NO HOSTS CONFIGURED, CAN'T BROADCAST INCLUDE FILES")
        return

    if options.verbose():
        print(f"BROADCAST[{dir}] <--- {files}")


    for filename in tqdm(files):
        path = os.path.join(dir, filename)
        content = read_binary_content(path)   

        serializer.add(path, content)
        if serializer.size() >= MAX_UPLOAD_SIZE:
            await do_broadcast_of_serialized_data(session, serializer, hosts, sslcontext)

    if serializer.size() > 0:
        await do_broadcast_of_serialized_data(session, serializer, hosts, sslcontext)

    for filename in tqdm(files):
        path = os.path.join(dir, filename)        
        scheduled_broadcast_tasks[path] = False



def is_ignorable_dir(item):
    ignore_dirs = ["bin", "Licenses", "References", "Shortcuts"]    
    return item in ignore_dirs


async def install_directory(session: aiohttp.ClientSession, hosts: List[str], dir: str, sslcontext: ssl.SSLContext, scheduled_broadcast_tasks: Dict[str, bool], options: DistBuildOptions, serializer: Serializer):
    content = os.listdir(dir)
    
    print("examing dir " + dir)
    #print("content = " + str(content))
    files: List[str] = []
    for item in content:
        if item.startswith("."):
            print("IGNORE: " + item)
            continue
  
        fullpath = os.path.join(dir, item)
        #print(f"EXAMINE: {fullpath}")

        if os.path.isfile(fullpath):
            if is_header_file(item):
                #print('Copying header: ' + item)
                if os.path.isfile(fullpath):
                    files.append(item)
        elif os.path.isdir(fullpath):
            if not is_ignorable_dir(item):
                await install_directory(session, hosts, fullpath, sslcontext, scheduled_broadcast_tasks, options, serializer)

    await broadcast_files(session, hosts, dir, files, sslcontext, scheduled_broadcast_tasks, options, serializer)
        
    


class FileSystemObserver:
    scheduled_broadcast_tasks: Dict[str, bool]
    options: DistBuildOptions

    def __init__(self, session: aiohttp.ClientSession, hosts: List[str], sslcontext: ssl.SSLContext, loop, scheduled_broadcast_tasks: Dict[str, bool], options: DistBuildOptions):
        self.session = session
        self.hosts = hosts
        self.sslcontext = sslcontext
        self.loop = loop
        self.options = options
        self.scheduled_broadcast_tasks = scheduled_broadcast_tasks

    def dispatch(self, evt):
        src_path = evt.src_path
        print("got file system evt: " + src_path)

        serializer = Serializer()

        files = [src_path]

        if not src_path in self.scheduled_broadcast_tasks:
            asyncio.run_coroutine_threadsafe(broadcast_files(self.session, self.hosts, files, self.sslcontext, self.scheduled_broadcast_tasks, serializer), self.loop)
        elif not self.scheduled_broadcast_tasks[src_path]:
            if os.path.isfile(src_path) and is_header_file(src_path):
                self.scheduled_broadcast_tasks[src_path] = True
                asyncio.run_coroutine_threadsafe(broadcast_files(self.session, self.hosts, files, self.sslcontext, self.scheduled_broadcast_tasks, serializer), self.loop)
        else:
            # src_path is in self.scheduled_broadcast_tasks
            #if self.options.verbose():
            #    print(f"broadcast of change already scheduled: {src_path}, evt = {evt.event_type}")
            pass

async def create_ssl_context() -> ssl.SSLContext:
    sslcontext = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    #sslcontext.load_verify_locations('certs/server.pem')
    sslcontext.check_hostname = False
    sslcontext.verify_mode = ssl.CERT_NONE
    #sslcontext.load_cert_chain('certs/server.crt', 'certs/server.key')
    return sslcontext

async def sendData(loop, hosts, scheduled_broadcast_tasks, options: DistBuildOptions, session:ClientSession):
    serializer = Serializer()
    sslcontext = await create_ssl_context()
    for cdir in get_include_dirs():
        await install_directory(session, hosts, cdir, sslcontext, scheduled_broadcast_tasks, options, serializer)

    event_handler = FileSystemObserver(session, hosts, sslcontext, loop, scheduled_broadcast_tasks, options)
    observer = Observer()
    for cdir in get_include_dirs():
        observer.schedule(event_handler, cdir, recursive=True)
    observer.start()


def main():
    hosts = get_build_hosts()

    options = DistBuildOptions()

    session = aiohttp.ClientSession()    

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    scheduled_broadcast_tasks: Dict[str, bool] = {}

    loop = asyncio.get_event_loop()
    loop.run_until_complete(sendData(loop, hosts, scheduled_broadcast_tasks, options, session))

    print("waiting for dir-changes")
    #loop.run_forever()

    wait_for_incoming_requests()



main()