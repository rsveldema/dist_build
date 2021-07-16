from asyncio.subprocess import Process
import socket
from profiler import Profiler
from serializer import Serializer
from options import DistBuildOptions
from os import mkdir, getenv, path, makedirs, chdir
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
from config import get_syncer_host, storage_dir, num_available_cores
import asyncio
import pathlib
import time
from file_utils import get_all_but_last_path_component, is_a_directory_path, is_source_file, make_dir_but_last, path_join, read_content, uniform_filename, write_binary_to_file, write_text_to_file, read_binary_content, transform_filename_to_output_name, FILE_PREFIX_IN_FORM

ssl.match_hostname = lambda cert, hostname: True
ssl.HAS_SNI = False
options: DistBuildOptions



async def install_file(request: aiohttp.RequestInfo):    
    data = await request.post()
    raw_content = data['content']

    serializer = Serializer()
    ret = serializer.extract(raw_content)

    for pathprop in ret.keys():
        content = ret[pathprop]

        install_path = path_join(storage_dir(), pathprop)
        install_dir = path.dirname(install_path).replace('/', '\\')

        #if install_path.find("winerror.h") >= 0:
        #print(f"INSTALL DIR FOUND FOR {install_path} and {storage_dir()}")

        assert(install_path.find("dist_build") > 0)


        if options.verbose():
            print('going to install ' + path.basename(install_path))
            print(" AT  " + install_dir)

        if not path.isdir(install_dir):
            makedirs(install_dir)

        write_binary_to_file(install_path, content)

    return aiohttp.web.Response(text="ok")


performance_data=[]
num_current_jobs = 0

def add_performance_data():
    now = time.time()
    perf = {'x': now, 'y' : num_current_jobs}
    performance_data.append(perf)


def notify_new_job_started():
    global num_current_jobs
    num_current_jobs += 1
    add_performance_data()

def notify_job_done():
    global num_current_jobs
    num_current_jobs -= 1
    add_performance_data()


global_profiler: Profiler = None

async def show_status(request):
    response_data = {"profile":global_profiler.spent, "performance":performance_data}
    return aiohttp.web.json_response(response_data)


async def make_app(options: DistBuildOptions, profiler: Profiler):
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
    return app


class LocalBuildJob:
    cmdlist: typing.List[str]
    id: str
    env: typing.Dict[str, str]
    files: typing.Dict[str, str]
    options: DistBuildOptions
    user_include_roots: List[str]
    profiler: Profiler

    def __init__(self, cmdline: typing.List[str], env: typing.Dict[str, str], id:str, client_sslcontext, session, files: Dict[str, str], options: DistBuildOptions, user_include_roots: List[str], profiler: Profiler):
        self.cmdlist = json.loads(cmdline)
        self.env = env
        self.profiler = profiler
        self.id = id
        self.files = json.loads(files)
        self.client_sslcontext = client_sslcontext
        self.session = session
        self.options = options
        self.user_include_roots = user_include_roots
        
    def is_user_directory(self, filename:str):        
        filename = uniform_filename(filename)
        for k in self.user_include_roots:
            k = uniform_filename(k)
            print(f"TEST: {filename} startswith {k}")
            if filename.startswith(k):
                return True
        return False

    async def run(self):
        notify_new_job_started()
        self.save_files()
        self.change_include_dirs()
        self.change_debug_dirs()
        self.change_output_dirs()
        (retcode, result) = await self.exec_cmd()        
        await self.send_reply(retcode, result)
        notify_job_done()

    def change_debug_dirs(self):
        # when seeing: /FdCMakeFiles\cmTC_ea5a2.dir
        # we need to create this dir in the build dir         
        new_cmdline:List[str] = []
        opt_prefix = '/Fd'
        for orig in self.cmdlist:       
            if orig.startswith(opt_prefix):
                orig = orig[len(opt_prefix):]
                orig = uniform_filename(orig)
                new_debug_dir = storage_dir() + '/' + orig
                orig = opt_prefix + new_debug_dir
                makedirs(new_debug_dir, exist_ok=True)
            new_cmdline.append(orig)   
        self.cmdlist = new_cmdline

    def change_output_dirs(self):
        # when seeing: /FdCMakeFiles\cmTC_ea5a2.dir
        # we need to create this dir in the build dir         
        new_cmdline:List[str] = []
        opt_prefix_VC = '/Fo'
        opt_prefix_GCC = '-o'
        next_param_is_output_file = False
        for orig in self.cmdlist:       

            if next_param_is_output_file:
                next_param_is_output_file = False
                new_output_file = uniform_filename(orig)               
                new_output_file = get_all_but_last_path_component(new_output_file)
                makedirs(new_output_file, exist_ok=True)
            elif orig == opt_prefix_GCC:
                next_param_is_output_file = True
            elif orig.startswith(opt_prefix_VC):
                orig = orig[len(opt_prefix_VC):]
                new_debug_dir = uniform_filename(orig)
                #new_debug_dir = storage_dir() + '/' + orig
                orig = opt_prefix_VC + new_debug_dir
                if make_dir_but_last(new_debug_dir):
                    makedirs(new_debug_dir, exist_ok=True)
            new_cmdline.append(orig)   
        self.cmdlist = new_cmdline

    def change_include_dirs(self):
        new_cmdline:List[str] = []
        found_include_directive_for_next_option = False
        for orig in self.cmdlist:
            new_cmd = orig
            if found_include_directive_for_next_option:
                found_include_directive_for_next_option = False
                print(f"TEST ME HERE {orig}")
                if self.is_user_directory(orig):
                    orig = uniform_filename(orig) 
                    new_cmd = storage_dir() + orig
            if orig == '/I' or orig == '-I':
               found_include_directive_for_next_option = True
            elif orig.startswith('-I'):
                no_replacement = orig
                orig = orig[2:]

                print(f"TEST ME HERE2 {orig}")
                if self.is_user_directory(orig):
                    orig = uniform_filename(orig)
                    new_cmd = '-I' + storage_dir() + orig    
                else:
                    new_cmd = no_replacement      

            new_cmdline.append(new_cmd)   
        self.cmdlist = new_cmdline


    def save_files(self):
        self.profiler.enter()
        #print(str(self.files))
        for it in self.files:
            oldpath = it
            newpath = self.save_file(oldpath, self.files[it])
            print(f"SAVE FILES ====> {oldpath} vs {newpath}")
            self.patch_arg_refering_saved_file(oldpath, newpath)
        self.profiler.leave()

    def patch_arg_refering_saved_file(self, oldpath:str, newpath:str):
        #print("PATCH: " + oldpath + ' -> ' + newpath)
        new_cmdline = []
        for orig in self.cmdlist:
            if orig == oldpath:
                fixed = orig.replace(oldpath, newpath)
            else:
                fixed = orig
            new_cmdline.append( fixed )
        self.cmdlist = new_cmdline

    def save_file(self, old_path, content) -> str:
        old_path = uniform_filename(old_path)
        container_path = storage_dir() + '/' + old_path
        container_dir = path.dirname(container_path)
        makedirs(container_dir, exist_ok=True)
        write_text_to_file(container_path, content)
        #print("wrote " + container_path)
        return container_path


    async def exec_cmd(self) -> Tuple[int, str]:
        self.profiler.enter()
        exit_code = -1
        stderr = ""
        stdout = ""
        try:
            print("EXEC: " + str(self.cmdlist))

            program = self.cmdlist[0]
            args = self.cmdlist[1:]
            ret:Process = await asyncio.subprocess.create_subprocess_exec(stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, *self.cmdlist )

            #print("trying to wait")

            stdout, stderr = await ret.communicate()

            exit_code = ret.returncode

            #print(f"got stdout {stdout}, ret {exit_code}")

            stdout = stdout.decode()
            stderr = stderr.decode()

        except FileNotFoundError as e:
            stderr = f"failed to find file: {self.cmdlist}"
        except Exception as e:
            stderr = f"unknown error during run of {self.cmdlist}, {e}"

        result_data = {
            "exit_code" : exit_code,
            "stderr" : stderr,
            "stdout" : stdout
        }

        self.profiler.leave()
        return (exit_code, json.dumps(result_data))
        
    def get_explicit_output_file(self):
        gcc_output_path = "-o"
        msvc_output_path = "/Fo"

        next_is_winner = False
        for param in self.cmdlist:
            if next_is_winner:
                return param
            if param == gcc_output_path:
                next_is_winner = True
                pass
            elif param.startswith(gcc_output_path):
                return param[len(gcc_output_path):]
            elif param.startswith(msvc_output_path) and not is_a_directory_path(param):
                return param[len(msvc_output_path):]
        return None


    def get_output_path(self):        
        vs_output_path = "/Fo"
        for param in self.cmdlist:
            if param.startswith(vs_output_path) and is_a_directory_path(param):
                return param[len(vs_output_path):]
        return None

    def is_using_microsoft_compiler(self):
        compiler_name = self.cmdlist[0].lower()
        if compiler_name.endswith("cl.exe"):
            return True        
        return False

    def append_output_files(self, outfiles: Dict[str, bytes]):    
        explicit_out = self.get_explicit_output_file()
        if explicit_out != None:
            print("using explicit output: " + explicit_out)
            outfiles[explicit_out] = read_binary_content(explicit_out)
            return

        is_microsoft = self.is_using_microsoft_compiler()
        for p in self.cmdlist:
            if is_source_file(p):
                output_file = transform_filename_to_output_name(p, is_microsoft, self.get_output_path())
                #print("output file ==== " + output_file)
                try:
                    outfiles[output_file] = read_binary_content(output_file)
                except FileNotFoundError as e:
                    print("ERROR: failed to find output file: " + output_file)


    async def send_reply(self, retcode, result:str):
        self.profiler.enter()
        outfiles: typing.Dict[str, bytes] = {}

        if retcode == 0:
            self.append_output_files(outfiles)

        #print(f"output files are {outfiles}")

        syncer_host = get_syncer_host()
        uri = syncer_host + '/notify_compile_job_done'
        #print("trying " + uri)
        data = FormData()
        data.add_field('result', result)
        data.add_field('id', self.id)
        for file in outfiles:
            data.add_field(FILE_PREFIX_IN_FORM + file, outfiles[file])
        r:ClientResponse = await self.session.post(uri, data = data, ssl=self.client_sslcontext)
        
        if r.status != 200:
            print("failed to send " + uri)
        self.profiler.leave()


async def try_fetch_compile_job(session: ClientSession, client_sslcontext, syncer_host, jobid: int, profiler: Profiler) -> LocalBuildJob:
    uri = syncer_host + '/pop_compile_job'
    print(f"job {jobid}: trying " + uri)
    data = FormData()
    data.add_field('machine_id', socket.gethostname()) 
    try:
        client_response = await session.post(uri, data = data, ssl=client_sslcontext)
    except:
        print(f"job {jobid}: failed to fetch a job from the syncer, trying again later")
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
        print("failed to decode json: " + e)
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
            print(f"task {jobid} succeeded in fetching a job")            
            await job.run()
        else:
            # if a job-fetch failed, we'll start slowing down
            await asyncio.sleep(1)




def main():
    global server_sslcontext, options
        
    profiler = Profiler()

    options = DistBuildOptions()

    server_sslcontext = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    server_sslcontext.load_cert_chain('certs/server.crt', 'certs/server.key')

    print("CHANGING RUN DIR TO " + storage_dir())
    chdir(storage_dir())

    loop = asyncio.get_event_loop()

    for i in range(1): #num_available_cores()):
        loop.create_task(poll_job_queue(i, profiler))

    aiohttp.web.run_app(make_app(options, profiler), ssl_context=server_sslcontext)


main()

