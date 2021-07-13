import io
from file_utils import deserialize_all_files_from_stream_no_meta, serialize_file_to_stream
from typing import Dict
import os

class Serializer:
    data: bytearray

    def __init__(self):
        self.data = bytearray()
        self.count = 0

    def clear(self):
        #print(f"{self.count}: CLEARING")
        self.data = bytearray()

    def payload(self) -> bytearray:
        return self.data

    def add(self, path: str, content: bytes):
        #if path.find('winerror') >= 0:
        #   print(f"{self.count}: SERIALIZING THIS THING: " + path)
        serialize_file_to_stream(self.data, path, content)
        self.count += 1

    def extract(self, data:bytes):
        ret: Dict[str, bytes] = {}
        inData =  io.BytesIO(data)
        deserialize_all_files_from_stream_no_meta(inData, ret)
        return ret

    def size(self) -> int:
        return len(self.data)


