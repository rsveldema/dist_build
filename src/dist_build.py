from asyncio.subprocess import Process
from src.config import current_user
from src.file_utils import create_client_ssl_context, get_all_but_last_path_component
import subprocess
from typing import List
from aiohttp.client import ClientSession
from config import get_syncer_host
import json
import ssl
import os
import io
import sys
import aiohttp
import asyncio
import logging
from file_utils import RESULT_DUMMY_FILENAME, is_source_file, read_content, deserialize_all_files_from_stream, uniform_filename, write_binary_to_file
import sys


async def kill_compile_job(session:ClientSession, client_sslcontext: ssl.SSLContext, syncer_host:str):
    uri = syncer_host + '/kill_compile_jobs'

    data = aiohttp.FormData()
    r = await session.post(uri, data = data, ssl=client_sslcontext)
    body = await r.read()
    print(f"kill-body = {body}")

def unpack_string(str:bytes):
    decoded = str.decode()
    #print("decoded === " + decoded)
    if decoded.startswith('b\''):
        decoded = decoded[2:-1]
    return decoded


async def sendCleanRequestToSyncer(loop, cmdline, syncer_host):   
    async with aiohttp.ClientSession() as session:
        client_sslcontext = create_client_ssl_context()
        uri = syncer_host + '/clean'
        data = aiohttp.FormData()
        data.add_field('username', current_user())
        r = await session.post(uri, data = data, ssl=client_sslcontext)
        body = await r.read()
        print(f"response: {body.decode()}")

async def sendInstallRequestToSyncer(loop, cmdline, syncer_host):   
    async with aiohttp.ClientSession() as session:
        client_sslcontext = create_client_ssl_context()
        uri = syncer_host + '/install'
        data = aiohttp.FormData()
        data.add_field('username', current_user())
        r = await session.post(uri, data = data, ssl=client_sslcontext)
        body = await r.read()
        print(f"response: {body.decode()}")

async def sendStatusRequestToSyncer(loop, cmdline, syncer_host):   
    async with aiohttp.ClientSession() as session:
        client_sslcontext = create_client_ssl_context()
        uri = syncer_host + '/status'
        r = await session.get(uri, ssl=client_sslcontext)
        body = await r.read()
        print(f"response: {body.decode()}")


async def start_compile_job(session:ClientSession, client_sslcontext: ssl.SSLContext, cmdline:str, syncer_host:str):
    uri = syncer_host + '/push_compile_job'
    files = {}

    # Strip away c: and add all .c/.cpp files to the 'files' dict
    new_cmdline = []
    for opt in cmdline:
        if is_source_file(opt):
            uniform = uniform_filename(opt)
            files[uniform] = read_content(opt)
            new_cmdline.append(uniform)
        else:
            new_cmdline.append(opt)
    cmdline = new_cmdline
    

    data = aiohttp.FormData()
    data.add_field('files', json.dumps(files))
    data.add_field('cmdline', json.dumps(cmdline))
    data.add_field('env', json.dumps(dict(os.environ)))
    #print("start----------------")
    r = await session.post(uri, data = data, ssl=client_sslcontext)
    body = await r.read()
    all_files = deserialize_all_files_from_stream(io.BytesIO(body))
    #print(f"received {len(all_files)} files")

    result = all_files[RESULT_DUMMY_FILENAME]
    #print("REAULT++++++ " + str(result))
    result = json.loads(result)

    error_code = result["exit_code"]
    stdout_str:str= result["stdout"]
    stderr_str:str = result["stderr"]
    #print("RESULT = " + str(error_code) + ", STDOUT = " + stdout + ", STDERR = " + stderr)

    sys.stderr.write(f"{unpack_string(stderr_str.encode())}")  

    for k in stdout_str.split('\n'):
        if not k.startswith("Note: including"):
            sys.stdout.write(k)

    for filename in all_files:
        if filename != RESULT_DUMMY_FILENAME:
            write_filename = uniform_filename(filename)
            try:
                content = all_files[filename]
                print("WRITING FILE: " + write_filename + ", len = " + str(len(content)))
                write_binary_to_file(write_filename, content)
            except Exception as e:
                logging.error("failed to write " + write_filename)
                error_code = -1

    sys.exit(error_code)


async def sendCompilationRequestToSyncer(loop, cmdline, syncer_host):
    async with aiohttp.ClientSession() as session:
        client_sslcontext = create_client_ssl_context()
        
        try:
            await start_compile_job(session, client_sslcontext, cmdline, syncer_host)
        except KeyboardInterrupt:
            await kill_compile_job(session, client_sslcontext, syncer_host)




# only distribute pure compile jobs:
def is_link_job(cmdlist: List[str]):
    for opt in cmdlist:
        opt = opt.lower()
        if opt == "-c" or opt ==  "/c":
            return False
        if opt == "/link":
            return True
    return True




def run_cmd_locally(cmdline): 

    print("LOCAL JOB!!!!!\n")
    ret:subprocess.CompletedProcess = subprocess.run(cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    exit_code = ret.returncode

    #print(f"got stdout {stdout}, ret {exit_code}")

    stdout = ret.stdout
    stderr = ret.stderr

    sys.stderr.write(unpack_string(stderr))
    sys.stdout.write(unpack_string(stdout))

    sys.exit(exit_code)


def main():
    cmdline:List[str] = sys.argv[1:]

    if len(cmdline) == 0:
        print("Usage: dist_build.py <compiler> <compiler arguments>")
        sys.exit(1)

    loop = asyncio.get_event_loop()
    if cmdline[0] == "clean":
        loop.run_until_complete(sendCleanRequestToSyncer(loop, cmdline, get_syncer_host()))
        return
    elif cmdline[0] == "install":
        loop.run_until_complete(sendInstallRequestToSyncer(loop, cmdline, get_syncer_host()))
        return
    elif cmdline[0] == "status":
        loop.run_until_complete(sendStatusRequestToSyncer(loop, cmdline, get_syncer_host()))
        return

    if is_link_job(cmdline):
        run_cmd_locally(cmdline)
    else:
        loop.run_until_complete(sendCompilationRequestToSyncer(loop, cmdline, get_syncer_host()))


if __name__ == "__main__":
    main()