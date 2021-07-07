from os import mkdir, getenv, path, makedirs, chdir
import ssl
import typing
import json
import base64
from typing import Dict, List
import aiohttp
from aiohttp.formdata import FormData
from aiohttp_session import setup, get_session, session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography import fernet
from config import storage_dir
import asyncio
import subprocess
from file_utils import is_source_file, read_config, read_content, write_text_to_file, read_binary_content, transform_filename_to_output_name, FILE_PREFIX_IN_FORM

config = read_config()

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
    cmdlist: typing.List[str]
    id: str
    env: typing.Dict[str, str]
    files: typing.Dict[str, str]

    def __init__(self, cmdline: typing.List[str], env: typing.Dict[str, str], id:str, client_sslcontext, session, files: Dict[str, str]):
        self.cmdlist = json.loads(cmdline)
        self.env = env
        self.id = id
        self.files = json.loads(files)
        self.client_sslcontext = client_sslcontext
        self.session = session
        
    async def run(self):
        self.save_files()
        result = self.exec_cmd()
        await self.send_reply(result)

    def save_files(self):
        print(str(self.files))
        for it in self.files:
            oldpath = it
            newpath = self.save_file(oldpath, self.files[it])
            self.patch_arg(oldpath, newpath)

    def patch_arg(self, oldpath:str, newpath:str):
        print("PATCH: " + oldpath + ' -> ' + newpath)
        new_cmdline = []
        for orig in self.cmdlist:
            fixed = orig.replace(oldpath, newpath)
            new_cmdline.append( fixed )
        self.cmdlist = new_cmdline

    def save_file(self, old_path, content) -> str:
        container_path = storage_dir() + '/' + old_path
        container_dir = path.dirname(container_path)
        makedirs(container_dir, exist_ok=True)
        write_text_to_file(container_path, content)
        print("wrote " + container_path)
        return container_path


    def exec_cmd(self) -> str:
        try:
            print("EXEC: " + str(self.cmdlist))
            ret = subprocess.run(self.cmdlist, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            return json.dumps((ret.returncode, str(ret.stderr) + str(ret.stdout)))
        except FileNotFoundError as e:
            return json.dumps("failed to find file: " + self.cmdline)
        except:
            return json.dumps("unknown error during run of " + self.cmdline)


    def get_output_path(self):        
        vs_output_path = "/Fo"
        for param in self.cmdlist:
            if param.startswith(vs_output_path):
                return param[len(vs_output_path):]
        return None

    def is_using_microsoft_compiler(self):
        compiler_name = self.cmdlist[0].lower()
        if compiler_name.endswith("cl.exe"):
            return True        
        return False

    def append_output_files(self, outfiles: Dict[str, bytes]):
        is_microsoft = self.is_using_microsoft_compiler()
        for p in self.cmdlist:
            if is_source_file(p):
                output_file = transform_filename_to_output_name(p, is_microsoft, self.get_output_path())
                print("output file ==== " + output_file)
                try:
                    outfiles[output_file] = read_binary_content(output_file)
                except FileNotFoundError as e:
                    print("ERROR: failed to find output file: " + output_file)


    async def send_reply(self, result):
        output_path = self.get_output_path()

        outfiles: typing.Dict[str, bytes] = {}

        self.append_output_files(outfiles)

        syncer_host = config['syncer']
        uri = syncer_host + '/notify_compile_job_done'
        print("trying " + uri)
        data = FormData()
        data.add_field('result', result)
        data.add_field('id', self.id)
        for file in outfiles:
            data.add_field(FILE_PREFIX_IN_FORM + file, outfiles[file])
        r = await self.session.post(uri, data = data, ssl=self.client_sslcontext)
        print("notifying syncer")


async def try_fetch_compile_job(session, client_sslcontext, syncer_host) -> LocalBuildJob:    
    uri = syncer_host + '/pop_compile_job'
    print("trying " + uri)
    data=FormData()
    try:
        r = await session.post(uri, data = data, ssl=client_sslcontext)
    except:
        print("failed to fetch a job from the syncer, trying again later")
        return None
    
    text = await r.text()
    if text == "ok":
        return None

    try:
        payload = json.loads(text)
        if "cmdline" in payload:
            env = payload['env']
            cmdline = payload['cmdline']
            id = payload['id']
            files = payload['files']
            #print("remote compile activated: " + cmdline)
            return LocalBuildJob(cmdline, env, id, client_sslcontext, session, files)
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


print("CHANGING RUN DIR TO " + storage_dir())
chdir(storage_dir())

aiohttp.web.run_app(make_app(), ssl_context=server_sslcontext)
