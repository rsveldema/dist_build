from os import mkdir, getenv, path, makedirs
import ssl
import time
import base64
from aiohttp import web
from aiohttp_session import setup, get_session, session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography import fernet


ssl.match_hostname = lambda cert, hostname: True
ssl.HAS_SNI = False


def storage_dir():
    home = getenv("HOME")
    if home == None:
        home = "c:/"
    storage = home + '/dist_build'
    return storage


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

    fp = open(install_path, 'wb')
    fp.write(content)
    fp.close()    
    return web.Response(text="ok")




async def make_app():
    app = web.Application()
    # secret_key must be 32 url-safe base64-encoded bytes
    fernet_key = fernet.Fernet.generate_key()
    secret_key = base64.urlsafe_b64decode(fernet_key)
    setup(app, EncryptedCookieStorage(secret_key))
    app.add_routes([web.post('/install_file', install_file)])
    return app


sslcontext = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
sslcontext.load_cert_chain('certs/server.crt', 'certs/server.key')

web.run_app(make_app(), ssl_context=sslcontext)