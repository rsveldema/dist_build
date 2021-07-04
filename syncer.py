import json
import requests
import os

header_suffix_list = ['.h', '.hh', '.hxx']

def is_header_file(filename):
    for h in header_suffix_list:
        if filename.endswith(h):
            return True
    return False


def install_directory(hosts: 'list[str]', dir: str):
    content = os.listdir(dir)
    print("content = " + str(content))
    files = []
    for item in content:
        if is_header_file(item):
            print('its a header: ' + item)
            if os.path.isfile(dir + '/' + item):
                files.append(item)

    print("all files = " + str(files))
    for filename in files:
        for host in hosts:
            uri = 'https://' + host + "/install_file"
            path = dir + '/' + filename
            fp = open(path)
            content = fp.read()
            fp.close()
            r = requests.post(uri, data = {'path': path, 'content': content}, verify='cert.pem')
            print("result = " + str(r))


fp = open('config.json')
config = json.loads(fp.read())
fp.close()

print("config = " + str(config))

hosts = config['hosts']

for cdir in config['dirs']:
    install_directory(hosts, cdir)
