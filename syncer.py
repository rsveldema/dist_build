import json
import ssl
import os
import logging

import aiohttp
import asyncio

header_suffix_list = ['.h', '.hh', '.hxx']


ssl.match_hostname = lambda cert, hostname: True


def is_header_file(filename):
    for h in header_suffix_list:
        if filename.endswith(h):
            return True
    return False


async def install_directory(s: aiohttp.ClientSession, hosts: 'list[str]', dir: str, sslcontext):
    content = os.listdir(dir)
    print("content = " + str(content))
    files = []
    for item in content:
        if is_header_file(item):
            print('its a header: ' + item)
            if os.path.isfile(dir + '/' + item):
                files.append(item)
            elif os.path.isdir(dir + '/' + item):
                install_directory(s, hosts, dir + '/' + item, sslcontext)

    print("all files = " + str(files))
    for filename in files:
        path = dir + '/' + filename
        fp = open(path, 'rb')
        content = fp.read()
        fp.close()
        print("file size = " + str(len(content)))
        for host in hosts:
            uri = 'https://' + host + "/install_file"
            data = aiohttp.FormData()
            data.add_field('path', path)
            data.add_field('content', content, content_type='application/octet-stream', content_transfer_encoding="binary") 
            print("start----------------")
            r = await s.post(uri, data = data, ssl=sslcontext)
            print("result = " + str(r))


fp = open('config.json')
config = json.loads(fp.read())
fp.close()

print("config = " + str(config))

hosts = config['hosts']

async def sendData():
    sslcontext = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    #sslcontext.load_verify_locations('certs/server.pem')
    sslcontext.check_hostname = False
    sslcontext.verify_mode = ssl.CERT_NONE
    #sslcontext.load_cert_chain('certs/server.crt', 'certs/server.key')

    s = aiohttp.ClientSession()    
    for cdir in config['dirs']:
        await install_directory(s, hosts, cdir, sslcontext)
    await s.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(sendData())