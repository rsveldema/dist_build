from os import getenv, makedirs
from typing import List
from file_utils import read_content
import json
import multiprocessing


def storage_dir():
    home = getenv("HOME")
    if home == None:
        home = "c:/"
    storage = home + '/dist_build'
    makedirs(storage, exist_ok=True)
    return storage


def read_config():
    content = read_content(storage_dir() + '/config.json')
    #print("config content ==  " + str(content))
    return json.loads(content)
        

config = read_config()

def get_syncer_host() -> str:
    return config['syncer']

def get_build_hosts() -> List[str]:
    return config['hosts']

def get_include_dirs() -> List[str]:
    return config['dirs']
    

def num_available_cores():
    if "num_cores" in config:
        return config["num_cores"]
    return int(multiprocessing.cpu_count() * 0.75)

