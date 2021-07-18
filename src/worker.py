from asyncio.subprocess import Process
import logging
import socket
from profiler import Profiler
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
from file_utils import safe_read_binary_content, file_exists, get_all_but_last_path_component, is_a_directory_path, is_source_file, make_dir_but_last, path_join, read_content, uniform_filename, write_binary_to_file, write_text_to_file, read_binary_content, transform_filename_to_output_name, FILE_PREFIX_IN_FORM
import shutil

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
        install_dir = os.path.dirname(install_path).replace('/', '\\')

        if options.verbose():
            logging.debug('going to install ' + os.path.basename(install_path))
            logging.debug(" AT  " + install_dir)

        if not os.path.isdir(install_dir):
            os.makedirs(install_dir)

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

    username = data['username'].decode()

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
    app.add_routes([aiohttp.web.get('/clean', worker_clean)])    
    return app


class LocalBuildJob:
    cmdlist: typing.List[str]
    id: str
    env: typing.Dict[str, str]
    files: typing.Dict[str, str]
    options: DistBuildOptions
    user_include_roots: List[str]
    profiler: Profiler

    def __init__(self, cmdline: typing.List[str], env: str, id:str, client_sslcontext, session, files: Dict[str, str], options: DistBuildOptions, user_include_roots: List[str], profiler: Profiler):
        self.cmdlist = json.loads(cmdline)
        self.env = json.loads(env)
        self.profiler = profiler
        self.id = id
        self.files = json.loads(files)
        self.client_sslcontext = client_sslcontext
        self.session = session
        self.options = options
        self.user_include_roots = user_include_roots
        self.username = self.env['USERNAME']
        
    def is_user_directory(self, filename:str):        
        filename = uniform_filename(filename)
        for k in self.user_include_roots:
            k = uniform_filename(k)
            #print(f"TEST: {filename} startswith {k}")
            if filename.startswith(k):
                return True
        return False

    async def run(self):
        notify_new_job_started()
        self.change_dir()
        self.save_files()
        self.change_include_dirs()
        self.change_debug_dirs()
        self.change_output_dirs()
        (retcode, result) = await self.exec_cmd()        
        await self.send_reply(retcode, result)
        notify_job_done()        
        os.chdir(source_storage_dir(self.username))
 
    def get_current_dir_from_env(self) ->str:
        found_env_cwd:str = None
        if "CWD" in self.env:
            found_env_cwd = self.env["CWD"]
        elif "PWD" in self.env:
            found_env_cwd = self.env["PWD"]

        if found_env_cwd != None:
            found_env_cwd  = uniform_filename(found_env_cwd)
            logging.debug("FOUND CWD/PWD in sent env: " + found_env_cwd)
            found_env_cwd = source_storage_dir(self.username) + '/' + found_env_cwd
            os.makedirs(found_env_cwd, exist_ok=True)
        return found_env_cwd

    def change_dir(self):
        cwd:str = self.get_current_dir_from_env()
        if cwd != None:
            os.chdir(cwd)
        else:
            print("failed to find CWD or PWD in env. variables. Can't change to original build dir in sandbox to allow relative includes to work")

    def change_debug_dirs(self):
        # when seeing: /FdCMakeFiles\cmTC_ea5a2.dir
        # we need to create this dir in the build dir         
        new_cmdline:List[str] = []
        opt_prefix = '/Fd'
        for orig in self.cmdlist:       
            if orig.startswith(opt_prefix):
                orig = orig[len(opt_prefix):]
                orig = uniform_filename(orig)
                new_debug_dir = source_storage_dir(self.username) + '/' + orig
                orig = opt_prefix + new_debug_dir
                os.makedirs(new_debug_dir, exist_ok=True)
            new_cmdline.append(orig)   
        self.cmdlist = new_cmdline


    def get_dependency_file(self):
        i = 0
        while (i < len(self.cmdlist)):
            orig = self.cmdlist[i]
            if orig == '-MF':
                i += 1
                orig = self.cmdlist[i]
            
                new_dep_dir = orig
                return new_dep_dir

            i += 1
        return None

    def change_output_dirs(self):
        # when seeing: /FdCMakeFiles\cmTC_ea5a2.dir
        # we need to create this dir in the build dir         
        new_cmdline:List[str] = []
        opt_prefix_VC = '/Fo'
        opt_prefix_GCC = '-o'

        i = 0
        while (i < len(self.cmdlist)):
            orig = self.cmdlist[i]

            if orig == '-MF':
                new_cmdline.append(orig)  
                i += 1
                orig = self.cmdlist[i]
            
                new_dep_dir = get_all_but_last_path_component(orig)
                os.makedirs(new_dep_dir, exist_ok=True)

            if orig == opt_prefix_GCC:
                new_cmdline.append(orig)  
                i += 1
                orig = self.cmdlist[i]
                new_output_file = uniform_filename(orig)               
                new_output_file = get_all_but_last_path_component(new_output_file)
                os.makedirs(new_output_file, exist_ok=True)
            elif orig.startswith(opt_prefix_VC):
                orig = orig[len(opt_prefix_VC):]
                new_debug_dir = uniform_filename(orig)
                #new_debug_dir = source_storage_dir(self.username) + '/' + orig
                orig = opt_prefix_VC + new_debug_dir
                if make_dir_but_last(new_debug_dir):
                    os.makedirs(new_debug_dir, exist_ok=True)

            new_cmdline.append(orig)  
            i += 1 

        self.cmdlist = new_cmdline

    def change_include_dirs(self):
        new_cmdline:List[str] = []
        found_include_directive_for_next_option = False
        for orig in self.cmdlist:
            new_cmd = orig
            if found_include_directive_for_next_option:
                found_include_directive_for_next_option = False
                #print(f"TEST ME HERE {orig}")
                if self.is_user_directory(orig):
                    orig = uniform_filename(orig) 
                    new_cmd = source_storage_dir(self.username) + orig
            if orig == '/I' or orig == '-I':
               found_include_directive_for_next_option = True
            elif orig.startswith('-I'):
                no_replacement = orig
                orig = orig[2:]

                #print(f"TEST ME HERE2 {orig}")
                if self.is_user_directory(orig):
                    orig = uniform_filename(orig)
                    new_cmd = '-I' + source_storage_dir(self.username) + orig    
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
            #print(f"SAVE FILES ====> {oldpath} vs {newpath}")
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

    def save_file(self, old_path:str, content) -> str:
        if old_path.startswith('.'):
            cwd:str = self.get_current_dir_from_env()
            container_path = cwd + '/' + old_path
        else:
            old_path = uniform_filename(old_path)
            container_path = source_storage_dir(self.username) + '/' + old_path
        
        container_dir = os.path.dirname(container_path)
        os.makedirs(container_dir, exist_ok=True)
        write_text_to_file(container_path, content)
        #print("wrote " + container_path)
        return container_path


    async def exec_cmd(self) -> Tuple[int, str]:
        self.profiler.enter()
        exit_code = -1
        stderr = ""
        stdout = ""
        try:
            logging.info("EXEC: " + str(self.cmdlist))

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
            logging.error(stderr)
        except Exception as e:
            stderr = f"unknown error during run of {self.cmdlist}, {e}"
            logging.error(stderr)

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
        dependency_file = self.get_dependency_file()
        if dependency_file != None:
            file_content =  safe_read_binary_content(dependency_file)
            if file_content != None:
                logging.debug("returning dependency file " + dependency_file)
                outfiles[dependency_file] = file_content

        explicit_out = self.get_explicit_output_file()
        if explicit_out != None:
            file_content = safe_read_binary_content(explicit_out)
            if file_content != None:
                outfiles[explicit_out] = file_content
            return

        is_microsoft = self.is_using_microsoft_compiler()
        for p in self.cmdlist:
            if is_source_file(p):
                output_file = transform_filename_to_output_name(p, is_microsoft, self.get_output_path())
                #print("output file ==== " + output_file)
                file_content = safe_read_binary_content(output_file)
                if file_content != None:
                    outfiles[output_file] = read_binary_content(output_file)


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
            logging.error("failed to send " + uri)
        self.profiler.leave()


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

    loop = asyncio.get_event_loop()

    for i in range(num_available_cores()):
        loop.create_task(poll_job_queue(i, profiler))

    aiohttp.web.run_app(make_app(options, profiler), ssl_context=server_sslcontext)


main()

