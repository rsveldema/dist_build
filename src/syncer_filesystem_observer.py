
import logging
from syncer_include_installer import broadcast_files
from typing import Dict, List
from options import DistBuildOptions
import aiohttp
import ssl
import os
from file_utils import is_header_file
from serializer import Serializer
import asyncio
from watchdog.observers import Observer
from config import get_build_hosts, get_include_dirs


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
        if os.path.isdir(src_path) or src_path.find("CMakeFiles") > 0:
            logging.info("IGNORING DIR EVENT: " + src_path)
            return

        if not is_header_file(src_path):
            logging.info("IGNORING NON HEADER: " + src_path)
            return

        logging.info("got file system evt: " + src_path)

        serializer = Serializer()

        dir = ""
        files = [src_path]

        if not src_path in self.scheduled_broadcast_tasks:
            asyncio.run_coroutine_threadsafe(broadcast_files(self.session, self.hosts, dir, files, self.sslcontext, self.scheduled_broadcast_tasks, self.options, serializer), self.loop)
        elif not self.scheduled_broadcast_tasks[src_path]:
            if os.path.isfile(src_path) and is_header_file(src_path):
                self.scheduled_broadcast_tasks[src_path] = True
                asyncio.run_coroutine_threadsafe(broadcast_files(self.session, self.hosts, dir, files, self.sslcontext, self.scheduled_broadcast_tasks, self.options, serializer), self.loop)
        else:
            # src_path is in self.scheduled_broadcast_tasks
            #if self.options.verbose():
            #    print(f"broadcast of change already scheduled: {src_path}, evt = {evt.event_type}")
            pass



async def install_filesystem_observer(session: aiohttp.ClientSession, sslcontext: ssl.SSLContext, loop, scheduled_broadcast_tasks: Dict[str, bool], options: DistBuildOptions):
    hosts = get_build_hosts()
    event_handler = FileSystemObserver(session, hosts, sslcontext, loop, scheduled_broadcast_tasks, options)
    observer = Observer()
    for cdir in get_include_dirs():
        observer.schedule(event_handler, cdir, recursive=True)
    observer.start()

