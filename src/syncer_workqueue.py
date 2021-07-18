import logging
import aiohttp

from aiohttp_session import setup
from aio_server import aio_server
from typing import Dict, List
from options import DistBuildOptions
from syncer_include_installer import async_install_headers
from config import get_include_dirs, get_copied_already_dirs, get_build_hosts
import ssl
import json
import base64
from aiohttp import web, ClientSession
import asyncio
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography import fernet
from file_utils import FILE_PREFIX_IN_FORM, serialize_all_files_to_stream, create_client_ssl_context
from urllib.parse import unquote

job_counter = 0
global_options: DistBuildOptions = None
global_session: aiohttp.ClientSession = None

class RemoteJob:
    files: Dict[str, str]
    to_send : Dict[str, bytes]
    cmdline: str
    machine_id: str
    is_killed: bool
    user_include_roots: List[str]

    def __init__(self, cmdline:str, env: dict, files: Dict[str, str], user_include_roots: List[str]):
        global job_counter
        self.files = files
        self.cmdline = cmdline
        self.env = env
        self.is_done = False
        self.id = str(job_counter)
        job_counter += 1
        self.machine_id = None
        self.user_include_roots = user_include_roots
        self.is_killed = False

    def kill(self):
        logging.debug(f"killing job at {self.machine_id}")       
        self.is_done = True
        self.is_killed = True

    def get_dict(self):
        return {"cmdline": self.cmdline, "env" : self.env, "id" : self.id, "files": self.files, "user_include_roots": self.user_include_roots}

    def set_machine_id(self, machine_id):
        self.machine_id = machine_id

    async def notify_done(self, result, to_send: Dict[str, bytes]):
        self.to_send = to_send
        self.result = result
        self.is_done = True

    async def done(self):
        #print("done flag = " + str(self.is_done))
        while not self.is_done:
            #print("done flag = " + str(self.is_done) + ', ' + str(len(job_queue))) 
            await asyncio.sleep(1)




job_queue: List[RemoteJob] = []
jobs_in_progress: Dict[str, RemoteJob] = {}



async def kill_compile_jobs(request):
    for j in jobs_in_progress:
        await j.kill()
    jobs_in_progress.clear()
    job_queue.clear()


async def push_compile_job(request):    
    data = await request.post()
    cmdline = data['cmdline']
    env = data['env']
    files = data['files']

    user_include_roots = get_include_dirs().copy()
    user_include_roots.extend(get_copied_already_dirs())

    job = RemoteJob(cmdline, env, files, user_include_roots)
    job_queue.append(job)
    jobs_in_progress[job.id] = job

    logging.debug("going to compile: " + cmdline)
    await job.done() 
    #print("compile done: " + cmdline)
    #return web.Response(text=job.result)
    
    #print(f"GO TO SEND: {job.to_send}")

    to_send = job.to_send
    stream_response = web.StreamResponse()
    stream_response.enable_chunked_encoding()
    await stream_response.prepare(request)    
    await serialize_all_files_to_stream(stream_response, to_send, job.result)
    await stream_response.write_eof()
    return stream_response



"""
sent by worker to syncer
"""
async def notify_compile_job_done(request):
    payload: List[str] = await request.post()
    id = payload['id']
    result = payload['result']

    to_send: Dict[str, bytes] = {}
    for p in payload:
        decoded_filename = unquote(p)
        logging.debug(f"EXAMINGING {decoded_filename}")
        if decoded_filename.startswith(FILE_PREFIX_IN_FORM):
            #print("FOUND OBJECT FILE: " + decoded_filename)
            out_file = decoded_filename[len(FILE_PREFIX_IN_FORM):]
            data:web.FileField = payload[p]
            to_send[out_file] = data.file.read()

    logging.debug("id = ==========> " + id)
    job = jobs_in_progress[id]
    await job.notify_done(result, to_send)
    return web.Response(text="ok")


async def pop_compile_job(request):
    payload: List[str] = await request.post()
    machine_id = payload['machine_id']

    for _retries in range(0, 10):
        if len(job_queue) > 0:
            new_job = job_queue.pop()
            logging.debug(f"MACHINE ID = {machine_id}")
            new_job.set_machine_id(machine_id)
            js = json.dumps(new_job.get_dict())
            return web.Response(text=js)
        await asyncio.sleep(1)
    return web.Response(text="ok")



async def handle_status_request(request):
    response = {}
    async with ClientSession() as session:
        client_sslcontext = create_client_ssl_context()

        for p in get_build_hosts():
            uri = "https://" + p + "/status"
            r = await session.get(uri, ssl=client_sslcontext)
            body = await r.read()
            logging.debug(f"received: {body}")

            response[p] = json.loads(body.decode())

    return web.json_response(response)

async def handle_clean_request(request):
    global global_session
    response = []
    session = global_session
    client_sslcontext = create_client_ssl_context()

    for p in get_build_hosts():
        uri = "https://" + p + "/clean"
        r = await session.get(uri, ssl=client_sslcontext)
        body = await r.read()
        logging.debug(f"received: {body}")

        response.append( json.loads(body.decode()) )

    return web.json_response(response)

async def handle_install_request(request):
    global global_session
    session = global_session
    client_sslcontext = create_client_ssl_context()
    scheduled_broadcast_tasks: Dict[str, bool] = {}
    stats = await async_install_headers(session, client_sslcontext, global_options, scheduled_broadcast_tasks)
    return web.json_response(json.dumps(stats.to_dict()))

async def make_app():
    app = web.Application()
    # secret_key must be 32 url-safe base64-encoded bytes
    fernet_key = fernet.Fernet.generate_key()
    secret_key = base64.urlsafe_b64decode(fernet_key)
    setup(app, EncryptedCookieStorage(secret_key))
    app.add_routes([
        web.post('/push_compile_job', push_compile_job),
        web.post('/kill_compile_jobs', kill_compile_jobs),
        web.post('/pop_compile_job', pop_compile_job),
        web.post('/notify_compile_job_done', notify_compile_job_done),
        web.get('/status', handle_status_request),
        web.post('/clean', handle_clean_request),
        web.post('/install', handle_install_request),
    ])
    return app


async def wait_for_incoming_requests(options: DistBuildOptions, session: aiohttp.ClientSession):
    global global_options
    global global_session

    global_session = session
    global_options = options

    server_sslcontext = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    server_sslcontext.load_cert_chain('certs/server.crt', 'certs/server.key')
  
    await aio_server(
                make_app(),
                #host=host,
                port=5000,
                #path=path,
                #sock=sock,
                #shutdown_timeout=shutdown_timeout,
                ssl_context=server_sslcontext,
                #print=print,
                #backlog=backlog,
                #access_log_class=access_log_class,
                #access_log_format=access_log_format,
                #access_log=access_log,
                #handle_signals=handle_signals,
                #reuse_address=reuse_address,
                #reuse_port=reuse_port,
            )