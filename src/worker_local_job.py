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

class LocalBuildJob:
    cmdlist: List[str]
    id: str
    env: Dict[str, str]
    files: Dict[str, str]
    options: options.DistBuildOptions
    user_include_roots: List[str]
    profiler: profiler.Profiler

    def __init__(self, cmdline: List[str], env: str, id:str, client_sslcontext, session, files: Dict[str, str], options: options.DistBuildOptions, user_include_roots: List[str], profiler: profiler.Profiler):
        self.cmdlist = json.loads(cmdline)
        self.env = json.loads(env)
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
        self.change_dir()
        self.save_files()
        self.change_include_dirs()
        self.change_debug_dirs()
        self.change_output_dirs()
        (retcode, result) = await self.exec_cmd()        
        await self.send_reply(retcode, result)
        profiler.notify_job_done()        
        #os.chdir(source_storage_dir(self.username))
 
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
            logging.info("CHDIR: " + cwd)
            os.chdir(cwd)
        else:
            print("failed to find CWD or PWD in env. variables. Can't change to original build dir in sandbox to allow relative includes to work")

    def change_debug_dirs(self):
        # when seeing: /FdCMakeFiles\cmTC_ea5a2.dir
        # we need to create this dir in the build dir         
        new_cmdline: List[str] = []
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
            #self.patch_arg_refering_saved_file(oldpath, newpath)
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
        
        container_path = uniform_filename(container_path)
        safe_write_text_to_file(container_path, content)
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
            proc:Process = await asyncio.subprocess.create_subprocess_exec(stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, *self.cmdlist )
            #print("trying to wait")
            #exit_code = await proc.wait()
            #stdout, stderr = await asyncio.wait_for(proc.communicate(), 1000)
            stdout, stderr = await proc.communicate()
            #proc.terminate()
            #await proc.wait()
            #await asyncio.sleep(0.5)

            exit_code = proc.returncode
            print(f"got stdout {stdout}, ret {exit_code} for {self.cmdlist}")

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

    async def append_output_files(self, outfiles: Dict[str, bytes]):
        dependency_file = self.get_dependency_file()
        if dependency_file != None:
            file_content = safe_read_binary_content(dependency_file)
            if file_content != None:
                logging.debug("returning dependency file " + dependency_file)
                outfiles[dependency_file] = file_content

        explicit_out = self.get_explicit_output_file()
        if explicit_out != None:
            file_content = safe_read_binary_content(explicit_out)
            if file_content != None:
                outfiles[explicit_out] = file_content
            else:
                logging.error("failed to safe-read: " + explicit_out)
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
        outfiles: Dict[str, bytes] = {}

        if retcode == 0:
            await self.append_output_files(outfiles)
        else:
            print(f"-------------------------RETODE {retcode} OFF FOR {self.cmdlist}")

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

