from flask import Flask, request, jsonify
from os import mkdir, getenv, path, makedirs
import ssl

app = Flask(__name__)

ssl.match_hostname = lambda cert, hostname: True
ssl.HAS_SNI = False


@app.route("/")
def hello():
    return "Hello World!"

def storage_dir():
    home = getenv("HOME")
    if home == None:
        home = "c:/"
    storage = home + '/dist_build'
    return storage

@app.route("/install_file", methods=['POST'])
def install_file():
    if request.method == 'POST':
        pathprop = request.form.get('path')
        content = request.form.get('content')      

        install_path = storage_dir() + pathprop
        filename = path.basename(install_path)
        install_dir = path.dirname(install_path).replace('/', '\\')

        print('going to install ' + filename)
        print(" AT  " + install_dir)

        if not path.isdir(install_dir):
            makedirs(install_dir)

        fp=open(install_path, 'wb')
        fp.write(content)
        fp.close()
    else:
        return "unhandled"
    return "ok"


if __name__ == "__main__":
    app.run(ssl_context=('certs/server.crt', 'certs/server.key'))

