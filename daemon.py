from os import mkdir, getenv, path, makedirs
import ssl
import json
import base64
from typing import Text
import aiohttp
from aiohttp.formdata import FormData
from aiohttp_session import setup, get_session, session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography import fernet
from config import storage_dir
import asyncio
import subprocess


with open('config.json') as fp:
    config = json.loads(fp.read())

ssl.match_hostname = lambda cert, hostname: True
ssl.HAS_SNI = False


async def install_file(request):    
    data = await request.post()
    pathprop = data['path']
    content = data['content']

    install_path = storage_dir() + pathprop
    filename = path.basename(install_path)
    install_dir = path.dirname(install_path).replace('/', '\\')

    print('going to install ' + filename)
    print(" AT  " + install_dir)

    if not path.isdir(install_dir):
        makedirs(install_dir)

    with open(install_path, 'wb') as fp:
        fp.write(content)
    return aiohttp.web.Response(text="ok")




async def make_app():
    app = aiohttp.web.Application()
    # secret_key must be 32 url-safe base64-encoded bytes
    fernet_key = fernet.Fernet.generate_key()
    secret_key = base64.urlsafe_b64decode(fernet_key)
    setup(app, EncryptedCookieStorage(secret_key))
    app.add_routes([aiohttp.web.post('/install_file', install_file)])
    return app


class LocalBuildJob:
    def __init__(self, cmdline: str, env: dict, id, client_sslcontext, session):
        self.cmdline = cmdline
        self.env = env
        self.id = id
        self.client_sslcontext = client_sslcontext
        self.session = session

    async def run(self):
        result = self.exec_cmd()
        await self.send_reply(result)

    def exec_cmd(self):
        cmdlist = json.loads(self.cmdline)
        try:
            ret = subprocess.run(cmdlist, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            return json.dumps((ret.returncode, str(ret.stderr) + str(ret.stdout)))
        except FileNotFoundError as e:
            return json.dumps("failed to find file: " + self.cmdline)


    async def send_reply(self, result):
        syncer_host = config['syncer']
        uri = syncer_host + '/notify_compile_job_done'
        print("trying " + uri)
        data = FormData()
        data.add_field('result', result)
        data.add_field('id', self.id)
        r = await self.session.post(uri, data = data, ssl=self.client_sslcontext)
        print("notifying syncer")


async def try_fetch_compile_job(session, client_sslcontext, syncer_host) -> LocalBuildJob:    
    uri = syncer_host + '/pop_compile_job'
    print("trying " + uri)
    data=FormData()
    r = await session.post(uri, data = data, ssl=client_sslcontext)
    text = await r.text()
    if text == "ok":
        return None

    try:
        payload = json.loads(text)
        if "cmdline" in payload:
            env = payload['env']
            cmdline = payload['cmdline']
            id = payload['id']
            print("remote compile activated: " + cmdline)
            return LocalBuildJob(cmdline, env, id, client_sslcontext, session)
    except ValueError as e:
        print("failed to decode json: " + e)
    return None

async def poll_job_queue():
    session = aiohttp.ClientSession()    
    client_sslcontext = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    #sslcontext.load_verify_locations('certs/server.pem')
    client_sslcontext.check_hostname = False
    client_sslcontext.verify_mode = ssl.CERT_NONE
    #sslcontext.load_cert_chain('certs/server.crt', 'certs/server.key')
    while True:
        job = await try_fetch_compile_job(session, client_sslcontext, config['syncer'])
        if job != None:
            await job.run()
        await asyncio.sleep(1)



loop = asyncio.get_event_loop()

loop.create_task(poll_job_queue())

server_sslcontext = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
server_sslcontext.load_cert_chain('certs/server.crt', 'certs/server.key')

aiohttp.web.run_app(make_app(), ssl_context=server_sslcontext)
