import ssl
import json
import base64
from aiohttp import web
import asyncio
from aiohttp.web_response import json_response
from aiohttp_session import setup, get_session, session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography import fernet
from typing import Dict, List
from file_utils import FILE_PREFIX_IN_FORM, serialize_all_files_to_stream
from urllib.parse import unquote

job_counter = 0

class RemoteJob:
    files: Dict[str, str]
    to_send : Dict[str, bytes]
    cmdline: str

    def __init__(self, cmdline:str, env: dict, files: Dict[str, str]):
        global job_counter
        self.files = files
        self.cmdline = cmdline
        self.env = env
        self.is_done = False
        self.id = str(job_counter)
        job_counter += 1

    def get_dict(self):
        return {"cmdline": self.cmdline, "env" : self.env, "id" : self.id, "files": self.files}

    async def notify_done(self, result, to_send: Dict[str, bytes]):
        self.to_send = to_send
        self.result = result
        self.is_done = True

    async def done(self):
        print("done flag = " + str(self.is_done))
        while not self.is_done:
            print("done flag = " + str(self.is_done) + ', ' + str(len(job_queue))) 
            await asyncio.sleep(1)

job_queue: 'list[RemoteJob]' = []
jobs_in_progress: 'dict[str, RemoteJob]' = {}

async def push_compile_job(request):    
    data = await request.post()
    cmdline = data['cmdline']
    env = data['env']
    files = data['files']

    job = RemoteJob(cmdline, env, files)
    job_queue.append(job)
    jobs_in_progress[job.id] = job

    print("going to compile: " + cmdline)
    await job.done() 
    print("compile done: " + cmdline)
    #return web.Response(text=job.result)
    
    print(f"GO TO SEND: {job.to_send}")

    to_send = job.to_send
    stream_response = web.StreamResponse()
    stream_response.enable_chunked_encoding()
    await stream_response.prepare(request)    
    await serialize_all_files_to_stream(stream_response, to_send)
    await stream_response.write_eof()
    return stream_response



"""
sent by daemon to syncer
"""
async def notify_compile_job_done(request):
    payload: List[str] = await request.post()
    id = payload['id']
    result = payload['result']

    to_send: Dict[str, bytes] = {}
    for p in payload:
        decoded_filename = unquote(p)
        print(f"EXAMINGING {decoded_filename}")
        if decoded_filename.startswith(FILE_PREFIX_IN_FORM):
            print("FOUND OBJECT FILE: " + decoded_filename)
            out_file = decoded_filename[len(FILE_PREFIX_IN_FORM):]
            data:web.FileField = payload[p]
            to_send[out_file] = data.file.read()

    print("id = ==========> " + id)
    job = jobs_in_progress[id]
    await job.notify_done(result, to_send)
    return web.Response(text="ok")

async def pop_compile_job(request):
    for i in range(0, 10):
        if len(job_queue) > 0:
            new_job = job_queue.pop()
            js = json.dumps(new_job.get_dict())
            return web.Response(text=js)
        await asyncio.sleep(1)
    return web.Response(text="ok")

async def make_app():
    app = web.Application()
    # secret_key must be 32 url-safe base64-encoded bytes
    fernet_key = fernet.Fernet.generate_key()
    secret_key = base64.urlsafe_b64decode(fernet_key)
    setup(app, EncryptedCookieStorage(secret_key))
    app.add_routes([
        web.post('/push_compile_job', push_compile_job),
        web.post('/pop_compile_job', pop_compile_job),
        web.post('/notify_compile_job_done', notify_compile_job_done),
    ])
    return app


def wait_for_incoming_requests():
    server_sslcontext = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    server_sslcontext.load_cert_chain('certs/server.crt', 'certs/server.key')
    web.run_app(make_app(), ssl_context=server_sslcontext, port=5000)
