import os
from file_utils import uniform_filename
from typing import List
from file_utils import read_content
import json
import logging
import multiprocessing
try:
  import pwd
except ImportError:
  import getpass
  pwd = None

def current_user():
  if pwd:
    return pwd.getpwuid(os.geteuid()).pw_name
  else:
    return getpass.getuser()

_MACRO_START_CHAR = '$'

def find_macro(p:str):
    ix = p.find(_MACRO_START_CHAR)
    if ix >= 0:
        ix += 1
        start = ix
        
        while ix < len(p):
            if not p[ix].isalnum():
                return p[start:ix]
            ix += 1
    return None

def expand_env_vars_in_array(paths:List[str]) -> List[str]:
    newpaths:List[str] = []
    for p in paths:
        logging.debug(f"examining: {p} for macro expansions")
        macro = find_macro(p)
        if macro != None:
            replacement_string = os.getenv(macro)
            if replacement_string != None:
                replacement_string = uniform_filename(replacement_string)
                p = p.replace(_MACRO_START_CHAR + macro, replacement_string)
            else:
                logging.error(f"failed to find env var '{macro}' used in '{p}'")
        newpaths.append(p)
    return newpaths


def storage_dir():
    home = os.getenv("HOME")
    if home == None:
        home = "c:/"
    storage = home + '/dist_build'
    os.makedirs(storage, exist_ok=True)
    return storage


def source_storage_dir(username):
    storage = storage_dir() + '/' + username
    os.makedirs(storage, exist_ok=True)
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
    return expand_env_vars_in_array(config['dirs'])
    

def get_copied_already_dirs() -> List[str]:
    if "copied_already" in config:
        return expand_env_vars_in_array(config['copied_already'])
    return []


def num_available_cores():
    if "num_cores" in config:
        return config["num_cores"]
    return int(multiprocessing.cpu_count() * 0.75)

