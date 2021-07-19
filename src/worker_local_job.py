from asyncio.subprocess import Process
import os
from time import sleep
import aiohttp
from config import get_syncer_host, source_storage_dir
from file_utils import FILE_PREFIX_IN_FORM, get_all_but_last_path_component, is_a_directory_path, is_source_file, make_dir_but_last, read_binary_content, safe_read_binary_content, safe_write_text_to_file, transform_filename_to_output_name, uniform_filename
import options
from typing import Dict, List, Tuple
import profiler
import json
import logging
import asyncio

def get_output_file_from_list(cmdlist):
    gcc_output_path = "-o"
    msvc_output_path = "/Fo"

    i = 0
    while i < len(cmdlist):
        param = cmdlist[i]
        if param == gcc_output_path:
            i += 1
            param = cmdlist[i]
            # todo: validate param
            return param
        elif param.startswith(gcc_output_path):
            return param[len(gcc_output_path):]
        elif param.startswith(msvc_output_path) and not is_a_directory_path(param):
            return param[len(msvc_output_path):]
        i += 1
    return None

def get_dep_file_from_cmdlist(cmdlist:List[str]) -> str:
    i = 0
    while (i < len(cmdlist)):
        orig = cmdlist[i]
        if orig == '-MF':
            i += 1
            orig = cmdlist[i]
            return orig

        i += 1
    return None
    
class LocalBuildJob:
    original_cmdlist: List[str]
    id: str
    env: Dict[str, str]
    files: Dict[str, str]
    options: options.DistBuildOptions
    user_include_roots: List[str]
    cached_current_dir: str
    profiler: profiler.Profiler

    def __init__(self, cmdline: List[str], env: str, id:str, client_sslcontext, session, files: Dict[str, str], options: options.DistBuildOptions, user_include_roots: List[str], profiler: profiler.Profiler):
        self.original_cmdlist = json.loads(cmdline)
        self.env = json.loads(env)
        self.cached_current_dir = None
        self.profiler = profiler
        self.id = id
        self.files = json.loads(files)
        self.client_sslcontext = client_sslcontext
        self.session = session
        self.options = options
        self.user_include_roots = user_include_roots
        self.username = "dummy"
        if "USERNAME" in self.env:
            self.username = self.env['USERNAME']
        elif "USER" in self.env:
            self.username = self.env['USER']
        
    def is_user_directory(self, filename:str):        
        filename = uniform_filename(filename)
        for k in self.user_include_roots:
            k = uniform_filename(k)
            #print(f"TEST: {filename} startswith {k}")
            if filename.startswith(k):
                return True
        return False

    async def run(self):
        profiler.notify_new_job_started()
        new_cmd_list = self.save_files(self.original_cmdlist)
        new_cmd_list = self.change_include_dirs(new_cmd_list)
        new_cmd_list = self.change_debug_dirs(new_cmd_list)
        new_cmd_list = self.change_output_dirs(new_cmd_list)
        (retcode, result) = await self.exec_cmd(new_cmd_list)        
        await self.send_reply(retcode, result, new_cmd_list)
        profiler.notify_job_done()        
 
    def get_current_dir_from_env(self) ->str:
        if self.cached_current_dir != None:
            return self.cached_current_dir

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
    
        self.cached_current_dir = found_env_cwd
        return found_env_cwd


    def change_debug_dirs(self, cmdlist: List[str]) -> List[str]:
        # when seeing: /FdCMakeFiles\cmTC_ea5a2.dir
        # we need to create this dir in the build dir         
        new_cmdline: List[str] = []
        opt_prefix = '/Fd'
        for orig in cmdlist:       
            if orig.startswith(opt_prefix):
                orig = orig[len(opt_prefix):]
                orig = uniform_filename(orig)
                new_debug_dir = source_storage_dir(self.username) + '/' + orig
                orig = opt_prefix + new_debug_dir
                os.makedirs(new_debug_dir, exist_ok=True)
            new_cmdline.append(orig)   
        return new_cmdline


    def get_original_dependency_file(self):
        return get_dep_file_from_cmdlist(self.original_cmdlist)

    def get_local_dependency_file(self, cmdlist: List[str]) -> str:
        filename = get_dep_file_from_cmdlist(cmdlist)
        if filename != None:
            new_dep_dir = self.relative_to_abs_dir(filename)
            return new_dep_dir
        return None

    def change_output_dirs(self, cmdlist:List[str]) -> List[str]:
        # when seeing: /FdCMakeFiles\cmTC_ea5a2.dir
        # we need to create this dir in the build dir         
        new_cmdline:List[str] = []
        opt_prefix_VC = '/Fo'
        opt_prefix_GCC = '-o'

        i = 0
        while (i < len(cmdlist)):
            orig = cmdlist[i]

            if orig == '-MF':
                new_cmdline.append(orig)  
                i += 1
                orig = cmdlist[i]
            
                new_dep_dir = get_all_but_last_path_component(orig)
                os.makedirs(new_dep_dir, exist_ok=True)
                orig = self.relative_to_abs_dir(orig)
            elif orig == opt_prefix_GCC:
                new_cmdline.append(orig)  
                i += 1
                orig = cmdlist[i]
                orig = self.relative_to_abs_dir(orig)

                new_output_dir = get_all_but_last_path_component(orig)
                os.makedirs(new_output_dir, exist_ok=True)
            elif orig.startswith(opt_prefix_VC):
                orig = orig[len(opt_prefix_VC):]
                orig = self.relative_to_abs_dir(orig)
                new_debug_dir = orig
                orig = opt_prefix_VC + orig
                if make_dir_but_last(new_debug_dir):
                    os.makedirs(new_debug_dir, exist_ok=True)

            new_cmdline.append(orig)  
            i += 1
        return new_cmdline



    def relative_to_abs_dir(self, path:str) -> str:
        path = uniform_filename(path)
        if path.startswith('/') or path.startswith('\\'):
            return path
        path = self.get_current_dir_from_env() + '/' + path
        return path


    def change_include_dirs(self, cmdlist: List[str]) -> List[str]:
        new_cmdline:List[str] = []
        i = 0
        while i < len(cmdlist):
            orig = cmdlist[i]
            new_cmd = orig

            if orig == '/I' or orig == '-I':
                # exactly -I means that the next item will be the path
                new_cmdline.append(new_cmd) 
                i += 1
                    
                orig = cmdlist[i]
                new_cmd = orig
                
                #print(f"TEST ME HERE {orig}")
                if self.is_user_directory(orig):
                    orig = uniform_filename(orig) 
                    new_cmd = source_storage_dir(self.username) + orig
                else:
                    new_cmd = self.relative_to_abs_dir(orig)
            elif orig.startswith('-I'):
                orig = orig[2:]

                #print(f"TEST ME HERE2 {orig}")
                if self.is_user_directory(orig):
                    orig = uniform_filename(orig)
                    new_cmd = '-I' + source_storage_dir(self.username) + orig    
                else:
                    new_cmd = '-I' + self.relative_to_abs_dir(orig)

            new_cmdline.append(new_cmd)   
            i += 1
        return new_cmdline


    def save_files(self, cmdlist: List[str]) -> List[str]:
        self.profiler.enter()
        #print(str(self.files))
        for it in self.files:
            oldpath = it
            newpath = self.save_file(oldpath, self.files[it])
            #print(f"SAVE FILES ====> {oldpath} vs {newpath}")
            cmdlist = self.patch_arg_refering_saved_file(oldpath, newpath, cmdlist)
        self.profiler.leave()
        return cmdlist

    def patch_arg_refering_saved_file(self, oldpath:str, newpath:str, cmdlist: List[str]) -> List[str]:
        #print("PATCH: " + oldpath + ' -> ' + newpath)
        new_cmdline = []
        for orig in cmdlist:
            if orig == oldpath:
                fixed = orig.replace(oldpath, newpath)
            else:
                fixed = orig
            new_cmdline.append( fixed )
        return new_cmdline

    def save_file(self, old_path:str, content) -> str:
        if old_path.startswith('.'):
            cwd:str = self.get_current_dir_from_env()
            container_path = cwd + '/' + old_path
        else:
            old_path = uniform_filename(old_path)
            container_path = source_storage_dir(self.username) + '/' + old_path
        
        container_path = uniform_filename(container_path)
        safe_write_text_to_file(container_path, content)
        #print("wrote " + container_path)
        return container_path


    async def exec_cmd(self, new_cmd_list: List[str]) -> Tuple[int, str]:
        self.profiler.enter()
        exit_code = -1
        stderr = ""
        stdout = ""
        try:
            logging.info("EXEC: " + str(new_cmd_list))

            proc:Process = await asyncio.subprocess.create_subprocess_exec(stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, *new_cmd_list )
            stdout, stderr = await proc.communicate()

            exit_code = proc.returncode
            print(f"got stdout {stdout}, ret {exit_code} for {new_cmd_list}")

            stdout = stdout.decode()
            stderr = stderr.decode()

        except FileNotFoundError as e:
            stderr = f"failed to find file: {new_cmd_list}"
            logging.error(stderr)
        except Exception as e:
            stderr = f"unknown error during run of {new_cmd_list}, {e}"
            logging.error(stderr)

        result_data = {
            "exit_code" : exit_code,
            "stderr" : stderr,
            "stdout" : stdout
        }

        self.profiler.leave()
        return (exit_code, json.dumps(result_data))
        

    def get_local_output_file(self, cmdlist):
        return get_output_file_from_list(cmdlist)
    
    def get_original_output_file(self):
        return get_output_file_from_list(self.original_cmdlist)

    def get_original_output_path(self):        
        vs_output_path = "/Fo"
        for param in self.original_cmdlist:
            if param.startswith(vs_output_path) and is_a_directory_path(param):
                return param[len(vs_output_path):]
        return None

    def is_using_microsoft_compiler(self):
        compiler_name = self.original_cmdlist[0].lower()
        if compiler_name.endswith("cl.exe"):
            return True        
        return False

    async def append_output_files(self, outfiles: Dict[str, bytes], cmdlist:List[str]):
        orig_dependency_file = self.get_original_dependency_file()

        if orig_dependency_file != None:
            local_dependency_file = self.get_local_dependency_file(cmdlist)
            assert local_dependency_file != None
            file_content = safe_read_binary_content(local_dependency_file)
            if file_content != None:
                logging.debug("returning dependency file " + orig_dependency_file)
                outfiles[orig_dependency_file] = file_content

        orig_explicit_out = self.get_original_output_file()
        if orig_explicit_out != None:
            local_explicit_out = self.get_local_output_file(cmdlist)
            assert local_explicit_out != None
            file_content = safe_read_binary_content(local_explicit_out)
            if file_content != None:
                outfiles[orig_explicit_out] = file_content
            else:
                logging.error("failed to safe-read: " + local_explicit_out)
            return

        is_microsoft = self.is_using_microsoft_compiler()
        for p in self.original_cmdlist:
            if is_source_file(p):
                output_file = transform_filename_to_output_name(p, is_microsoft, self.get_output_path())
                #print("output file ==== " + output_file)
                file_content = safe_read_binary_content(output_file)
                if file_content != None:
                    outfiles[output_file] = read_binary_content(output_file)


    async def send_reply(self, retcode, result:str, cmdlist:List[str]):
        self.profiler.enter()
        outfiles: Dict[str, bytes] = {}

        if retcode == 0:
            await self.append_output_files(outfiles, cmdlist)
        else:
            print(f"-------------------------RETODE {retcode} OFF FOR {cmdlist}")

        #print(f"output files are {outfiles}")

        syncer_host = get_syncer_host()
        uri = syncer_host + '/notify_compile_job_done'
        #print("trying " + uri)
        data = aiohttp.FormData()
        data.add_field('result', result)
        data.add_field('id', self.id)
        for file in outfiles:
            print(f"REPLY FILE: " + file)
            data.add_field(FILE_PREFIX_IN_FORM + file, outfiles[file])
        r:aiohttp.ClientResponse = await self.session.post(uri, data = data, ssl=self.client_sslcontext)
        
        if r.status != 200:
            logging.error("failed to send " + uri)
        self.profiler.leave()

