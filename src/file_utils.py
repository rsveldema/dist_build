import os
from typing import Dict
from aiohttp import web
import io

header_suffix_list = ['.h', '.hh', '.hxx', '.hpp', '.ver', '.ipp']
source_suffix_list = ['.c', '.cc', '.cxx', '.cpp']

RESULT_DUMMY_FILENAME="RESULT"
FILE_PREFIX_IN_FORM="FILE:"


"""
remove windows drive letter if prefixed with it
"""
def uniform_filename(filename) -> str:
    if filename.lower().startswith("c:"):
        filename = filename[2:]
    filename = filename.replace('/', '#')
    filename = filename.replace('\\', '#')
    filename = filename.replace('#', os.path.sep)
    return filename

def filename_ends_with(filename, suffix_list):
    filename = filename.lower()
    for h in suffix_list:
        if filename.endswith(h):
            return True
    return False

def is_a_directory_path(dir:str):
    return dir.endswith('/') or dir.endswith('\\')

def get_last_path_component(dir:str):
    dir = dir.strip()
    last1 = dir.rfind('/')
    last2 = dir.rfind('\\')
    last = max(last1, last2)
    if last > 0:
        dir = dir[last+1:]
    return dir

def get_all_but_last_path_component(dir:str):
    dir = dir.strip()
    last1 = dir.rfind('/')
    last2 = dir.rfind('\\')
    last = max(last1, last2)
    if last > 0:
        dir = dir[:last]
    return dir

def make_dir_but_last(dir:str):
    dir = dir.strip()
    if not is_a_directory_path(dir):
        dir = get_all_but_last_path_component(dir)
    os.makedirs(dir, exist_ok=True)

infra_files_substrings = ["README", "Makefile", "Doxyfile", "GNUmakefile", "boost-no-inspect"]
infra_files_exact = ["FAQ", "ChangeLog", "INDEX", "Makefile", "Jamfile", "LICENSE", "Doxyfile", "TODO", "configure", "Jenkinsfile"]

def is_infrastructure_file(filename:str):
    filename = filename.lower()
    filename = get_last_path_component(filename)
    if filename.startswith("."):
        return True
    for i in infra_files_substrings:
        i = i.lower()
        if filename.find(i) >= 0:
            return True
    for i in infra_files_exact:
        i = i.lower()
        if i == filename:
            return True
    return False

def is_source_file(filename:str):
    filename = filename.strip()
    if is_infrastructure_file(filename):
        return False
    return filename_ends_with(filename.lower(), source_suffix_list)
    
def is_header_file(filename):
    filename = filename.strip()
    filename = get_last_path_component(filename)
    if is_infrastructure_file(filename):
        return False
    if filename_ends_with(filename.lower(), header_suffix_list):
        return True
    # new style header files such as 'iostream' and 'cstddef'
    if filename.find(".") < 0:
        #print("its a header: " + filename)
        return True
    return False
 
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

    filename = uniform_filename(filename)

    prefix = ""
    rslash_pos = filename.rfind('\\')
    lslash_pos = filename.rfind('/')
    pos = rslash_pos
    if lslash_pos > pos:
        pos = lslash_pos

    ext = ".o"
    if is_microsoft:
        ext = ".obj"
        if output_path != None:
            prefix = output_path

            if pos > 0:
                filename = filename[pos + 1:]
    else:
        if pos > 0:
            filename = filename[pos + 1:]


    dot_pos = filename.rfind('.')
    if dot_pos < 0:
        dot_pos = len(filename)

    if prefix != None and prefix != "":
        prefix += os.path.pathsep

    print("CREATINGGGGG: " + prefix + filename[:dot_pos] + ext)
    return prefix + filename[:dot_pos] + ext



async def serialize_all_files_to_stream(stream_response: web.StreamResponse, outputs: Dict[str, bytes], result:str):
    await stream_response.write(len(result).to_bytes(4, 'little'))
    await stream_response.write(result.encode('utf-8'))
    for out_file in outputs:
        data = outputs[out_file]
        str_len = len(out_file)
        data_len = len(data)

        #print(f"SENDING {str_len} with len {data_len}")

        await stream_response.write(str_len.to_bytes(4, 'little'))
        await stream_response.write(out_file.encode('utf-8'))
        await stream_response.write(data_len.to_bytes(4, 'little'))
        await stream_response.write(data)


"""
same as the serialize_all_files_to_streams's loop body, compatiable to deserialize_all_files_from_stream_no_meta
"""        
def serialize_file_to_stream(data:bytearray, path, content):
        data.extend(len(path).to_bytes(4, 'little'))
        data.extend(path.encode('utf-8'))
        data.extend(len(content).to_bytes(4, 'little'))
        data.extend(content)


"""
compatible to serialize_all_files_to_stream's single string write
"""
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


deserialize_ix = 0

"""
compatible to serialize_all_files_to_stream's loop
"""
def deserialize_all_files_from_stream_no_meta(inData: io.BytesIO, ret: Dict[str, bytes]) -> None:
    global deserialize_ix
    while True:
        filename = read_bytes_from_stream(inData)
        if filename == None:
            break

        filename = filename.decode('utf-8')

        content = read_bytes_from_stream(inData)
        if content == None:
            break
        
        ret[filename] = content

        #if filename.find("winerror.h") > 0:
        #    print("FOUND It here: " + filename)
        #    print(f"{deserialize_ix}: DESERIALIZE {filename}")
    
        deserialize_ix += 1


"""
compatible to serialize_all_files_to_stream. The meta-data is stored in ret['RESULT'].
"""
def deserialize_all_files_from_stream(inData: io.BytesIO) ->  Dict[str, bytes]:
    ret: Dict[str, bytes] = {}

    result = read_bytes_from_stream(inData)
    ret[RESULT_DUMMY_FILENAME] = result

    deserialize_all_files_from_stream_no_meta(inData, ret)
    return ret


"""
We don't use os.path.join as on Windows it has strange behaviour (c:/a/b + /x --> c:/x)
"""
def path_join(p1:str, p2: str) -> str:
    if p1.endswith('/') or p1.endswith('\\'):
        return p1 + p2
    return p1 + os.sep + p2