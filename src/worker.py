from asyncio.subprocess import Process
import logging
import socket
from profiler import Profiler, get_worker_performance_data
from serializer import Serializer
from options import DistBuildOptions
import os
import ssl
import typing
import json
import base64
from typing import Dict, List, Tuple
import aiohttp
from aiohttp.client import ClientSession
from aiohttp.client_reqrep import ClientResponse
from aiohttp.formdata import FormData
from aiohttp_session import setup
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography import fernet
from config import get_syncer_host, source_storage_dir, num_available_cores
import asyncio
import pathlib
import time
from file_utils import safe_write_text_to_file, safe_read_binary_content, file_exists, get_all_but_last_path_component, is_a_directory_path, is_source_file, make_dir_but_last, path_join, read_content, uniform_filename, write_binary_to_file, write_text_to_file, read_binary_content, transform_filename_to_output_name, FILE_PREFIX_IN_FORM
import shutil
from worker_local_job import LocalBuildJob

ssl.match_hostname = lambda cert, hostname: True
ssl.HAS_SNI = False
options: DistBuildOptions



async def install_file(request: aiohttp.RequestInfo):    
    data = await request.post()
    raw_content = data['content']
    username = data['username'].decode()

    serializer = Serializer()
    ret = serializer.extract(raw_content)

    for pathprop in ret.keys():
        content = ret[pathprop]
        install_path = path_join(source_storage_dir(username), pathprop)
        write_binary_to_file(install_path, content)

    return aiohttp.web.Response(text="ok")


global_profiler: Profiler = None

async def show_status(request):
    response_data = {"profile":global_profiler.spent, "performance":get_worker_performance_data()}
    return aiohttp.web.json_response(response_data)

def onerror(func, path, exc_info):
    """
    Error handler for ``shutil.rmtree``.

    If the error is due to an access error (read only file)
    it attempts to add write permission and then retries.

    If the error is for another reason it re-raises the error.

    Usage : ``shutil.rmtree(path, onerror=onerror)``
    """
    import stat
    if not os.access(path, os.W_OK):
        # Is the error an access error ?
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise

async def worker_clean(request):  
    data = await request.post()

    username = data['username']

    keep = ["bin", "config.json"]
    result = "ok"

    for item in os.listdir(source_storage_dir(username)):
        if not (item in keep):
            path = source_storage_dir(username) + '/' + item
            logging.info("deleting " + path)
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path, onerror=onerror)
                else:
                    os.remove(path)
            except Exception as e:
                result = f"failed: {e}"
                
    response_data = {"host": socket.gethostname(), "result": result}
    return aiohttp.web.json_response(response_data)


async def make_app(options: DistBuildOptions, profiler: Profiler):
    # start the tasks to poll the syncer for new jobs:
    for i in range(num_available_cores()):
        asyncio.ensure_future( poll_job_queue(i, profiler) )


    global global_profiler
    # this server will only accept header files. We'll assume a 15 MByte upper limit on those.
    app = aiohttp.web.Application(client_max_size = 1024 * 1024 * 16)

    global_profiler = profiler
    
    # secret_key must be 32 url-safe base64-encoded bytes
    fernet_key = fernet.Fernet.generate_key()
    secret_key = base64.urlsafe_b64decode(fernet_key)
    setup(app, EncryptedCookieStorage(secret_key))
    app.add_routes([aiohttp.web.post('/install_file', install_file)])
    app.add_routes([aiohttp.web.get('/status', show_status)])
    app.add_routes([aiohttp.web.post('/clean', worker_clean)])    
    return app

async def try_fetch_compile_job(session: ClientSession, client_sslcontext, syncer_host, jobid: int, profiler: Profiler) -> LocalBuildJob:
    uri = syncer_host + '/pop_compile_job'
    logging.info(f"task {jobid}: trying " + uri)
    data = FormData()
    data.add_field('machine_id', socket.gethostname()) 
    try:
        client_response = await session.post(uri, data = data, ssl=client_sslcontext)
    except:
        logging.info(f"job {jobid}: failed to fetch a job from the syncer, trying again later")
        return None
    
    text = await client_response.text()
    if text == "ok":
        return None

    try:
        payload = json.loads(text)
        if "cmdline" in payload:
            env = payload['env']
            cmdline = payload['cmdline']
            id = payload['id']
            files = payload['files']
            user_include_roots = payload['user_include_roots']
            #print("remote compile activated: " + cmdline)
            return LocalBuildJob(cmdline, env, id, client_sslcontext, session, files, options, user_include_roots, profiler)
    except ValueError as e:
        logging.error("failed to decode json: " + e)
    return None

async def poll_job_queue(jobid: int, profiler: Profiler):
    session = aiohttp.ClientSession()    
    client_sslcontext = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    #sslcontext.load_verify_locations('certs/server.pem')
    client_sslcontext.check_hostname = False
    client_sslcontext.verify_mode = ssl.CERT_NONE
    #sslcontext.load_cert_chain('certs/server.crt', 'certs/server.key')
    while True:
        job = await try_fetch_compile_job(session, client_sslcontext, get_syncer_host(), jobid, profiler)
        if job != None:            
            logging.debug(f"task {jobid} succeeded in fetching a job")            
            await job.run()
        else:
            # if a job-fetch failed, we'll start slowing down
            await asyncio.sleep(1)




def main():
    global server_sslcontext, options
        
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
                        
    profiler = Profiler()

    options = DistBuildOptions()

    server_sslcontext = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    server_sslcontext.load_cert_chain('certs/server.crt', 'certs/server.key')

    aiohttp.web.run_app(make_app(options, profiler), ssl_context=server_sslcontext)


main()

