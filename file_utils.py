import json
from sys import path
from typing import Dict
from aiohttp import web
import io

header_suffix_list = ['.h', '.hh', '.hxx', '.hpp']
source_suffix_list = ['.c', '.cc', '.cxx', '.cpp']

FILE_PREFIX_IN_FORM="FILE:"

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
    with open(filename, 'r') as fp:
        return fp.read()

def read_binary_content(filename: str) -> bytes:
    with open(filename, 'rb') as fp:
        return fp.read()

def write_text_to_file(container_path, content):
    with open(container_path, 'w') as f:
        f.write(content)

def write_binary_to_file(container_path, content):
    with open(container_path, 'wb') as f:
        f.write(content)


def transform_filename_to_output_name(filename:str, is_microsoft: bool, output_path: str):
    prefix = ""

    ext = ".o"
    if is_microsoft:
        ext = ".obj"
        if output_path != None:
            prefix = output_path
            rslash_pos = filename.rfind('\\')
            lslash_pos = filename.rfind('/')
            pos = rslash_pos
            if lslash_pos > pos:
                pos = lslash_pos

            if pos > 0:
                filename = filename[pos:]

    dot_pos = filename.rfind('.')
    if dot_pos < 0:
        dot_pos = len(filename)
    return prefix + filename[:dot_pos] + ext



async def serialize_all_files_to_stream(stream_response: web.StreamResponse, outputs: Dict[str, bytes]):
    for out_file in outputs:
        data = outputs[out_file]
        str_len = len(out_file)
        data_len = len(data)

        #print(f"SENDING {str_len} with len {data_len}")

        await stream_response.write(str_len.to_bytes(4, 'little'))
        await stream_response.write(out_file.encode('utf-8'))
        await stream_response.write(data_len.to_bytes(4, 'little'))
        await stream_response.write(data)


def read_bytes_from_stream(inData: io.BytesIO):    
    str_len_buffer = inData.read(4)
    if len(str_len_buffer) == 0:
        # normal: EOF reached
        return None
    if len(str_len_buffer) != 4:
        print("ERROR: failed to read str-len")
        return None
    str_len = int.from_bytes(str_len_buffer, 'little')
    str = inData.read(str_len)
    return str

def deserialize_all_files_from_stream(inData: io.BytesIO) ->  Dict[str, bytes]:
    ret: Dict[str, bytes] = {}
 
    while True:
        filename = read_bytes_from_stream(inData)
        if filename == None:
            break

        content = read_bytes_from_stream(inData)
        if content == None:
            break
        
        ret[filename] = content

    return ret


