
import logging
import os
import sys
from config import get_build_hosts, get_include_dirs
from file_utils import is_header_file, read_binary_content, path_join
import ssl
from typing import Dict, List
from tqdm import tqdm
import aiohttp
from file_utils import create_client_ssl_context
from aiohttp.client import ClientSession
from serializer import Serializer, HeaderStatistics
from options import DistBuildOptions

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
                logging.error(f"post result = {post_result} when trying to send a header file chunk to daemon {host}")
                sys.exit(1)

        # print("result = " + str(r))
    serializer.clear()



async def broadcast_files(session: aiohttp.ClientSession, hosts: List[str], dir:str, files:List[str], sslcontext: ssl.SSLContext,
                         scheduled_broadcast_tasks: Dict[str, bool], options: DistBuildOptions, serializer: Serializer):   
    if len(hosts) == 0:
        logging.error("NO HOSTS CONFIGURED, CAN'T BROADCAST INCLUDE FILES")
        return

    if options.verbose():
        logging.debug(f"BROADCAST[{dir}] <--- {files}")


    for filename in tqdm(files):
        if dir == "":
            path = filename
        else:
            path = path_join(dir, filename)
        content = read_binary_content(path)   

        serializer.add(path, content)
        if serializer.size() >= MAX_UPLOAD_SIZE:
            await do_broadcast_of_serialized_data(session, serializer, hosts, sslcontext)

    if serializer.size() > 0:
        await do_broadcast_of_serialized_data(session, serializer, hosts, sslcontext)

    for filename in tqdm(files):
        if dir == "":
            path = filename
        else:
            path = path_join(dir, filename)
        scheduled_broadcast_tasks[path] = False



def is_ignorable_dir(item):
    ignore_dirs = ["bin", "Licenses", "References", "Shortcuts"]    
    return item in ignore_dirs


async def install_directory(session: aiohttp.ClientSession, hosts: List[str], dir: str, sslcontext: ssl.SSLContext, scheduled_broadcast_tasks: Dict[str, bool], options: DistBuildOptions, serializer: Serializer):
    content = os.listdir(dir)
    
    logging.info("examing dir " + dir)
    #print("content = " + str(content))
    files: List[str] = []
    for item in content:
        if item.startswith("."):
            logging.info("IGNORE: " + item)
            continue
  
        fullpath = path_join(dir, item)
        #print(f"EXAMINE: {fullpath}")

        if os.path.isfile(fullpath):
            if is_header_file(item):
                #print('Copying header: ' + item)
                if os.path.isfile(fullpath):
                    files.append(item)
            else:
                #print(f"skipping non-header: {item}")
                pass
        elif os.path.isdir(fullpath):
            if is_ignorable_dir(item):
                logging.info(f"ignorable dir: {item}")
            else:
                #print(f"recursing into {item}")
                await install_directory(session, hosts, fullpath, sslcontext, scheduled_broadcast_tasks, options, serializer)
        else:
            logging.error(f"WTF? not a FILE or DIR {fullpath}")
            

    await broadcast_files(session, hosts, dir, files, sslcontext, scheduled_broadcast_tasks, options, serializer)
        
    

async def broadcast_headers(hosts, sslcontext:ssl.SSLContext, scheduled_broadcast_tasks, options: DistBuildOptions, session:ClientSession) -> HeaderStatistics:
    serializer = Serializer()
    for cdir in get_include_dirs():
        await install_directory(session, hosts, cdir, sslcontext, scheduled_broadcast_tasks, options, serializer)
    return serializer.statistics

"""
returns the number of installed headers
"""
async def async_install_headers(session: aiohttp.ClientSession, sslcontext:ssl.SSLContext, options: DistBuildOptions, scheduled_broadcast_tasks: Dict[str, bool]) -> HeaderStatistics:
    hosts = get_build_hosts()
    stats = await broadcast_headers(hosts, sslcontext, scheduled_broadcast_tasks, options, session)
    return stats