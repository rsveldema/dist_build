import io
from file_utils import deserialize_all_files_from_stream_no_meta, serialize_file_to_stream
from typing import Dict

class HeaderStatistics:
    def __init__(self) -> None:
        self.file_count = 0
        self.total_bytes = 0

    def to_dict(self) -> Dict[str, int]:
        return {"file_count" : self.file_count, "total_bytes" : self.total_bytes}

class Serializer:
    data: bytearray
    statistics: HeaderStatistics

    def __init__(self):
        self.data = bytearray()
        self.count = 0
        self.statistics = HeaderStatistics()

    def clear(self):
        #print(f"{self.count}: CLEARING")
        self.data = bytearray()

    def payload(self) -> bytearray:
        return self.data

    def add(self, path: str, content: bytes):
        #if path.find('winerror') >= 0:
        #   print(f"{self.count}: SERIALIZING THIS THING: " + path)
        num_bytes = serialize_file_to_stream(self.data, path, content)
        self.count += 1

        self.statistics.total_bytes += num_bytes
        self.statistics.file_count += 1

    def extract(self, data:bytes):
        ret: Dict[str, bytes] = {}
        inData =  io.BytesIO(data)
        deserialize_all_files_from_stream_no_meta(inData, ret)
        return ret

    def size(self) -> int:
        return len(self.data)


