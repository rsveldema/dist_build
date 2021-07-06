import json
from sys import path

header_suffix_list = ['.h', '.hh', '.hxx', '.hpp']
source_suffix_list = ['.c', '.cc', '.cxx', '.cpp']

def filename_ends_with(filename, suffix_list):
    for h in suffix_list:
        if filename.endswith(h):
            return True
    return False

def is_source_file(filename:str):
    return filename_ends_with(filename, source_suffix_list)
    

def is_header_file(filename):
    return filename_ends_with(filename, header_suffix_list)
 
def read_content(filename: str):
    with open(filename) as fp:
        return fp.read()

def read_config():
    with open('config.json', 'r') as fp:
        return json.loads(fp.read())
        

def write_text_to_file(container_path, content):
    with open(container_path, 'w') as f:
        f.write(content)
