import time
import sys
import json



class StackFrame:
    def __init__(self, name: str):
        self.name = name
        self.start = time.time()

    def took(self):
        return time.time() - self.start

class Profiler:
    def __init__(self):
        self.callstack = []
        self.spent = {}

    def dump_stats(self):
        print("STATISTICS: ")
        print(json.dumps(self.spent))


    def enter(self):
        name =  sys._getframe().f_back.f_code.co_name
        self.callstack.append(StackFrame(name))

    def leave(self):
        frame = self.callstack.pop()

        if frame.name in self.spent:
            self.spent[frame.name] += frame.took()
        else:
            self.spent[frame.name] = frame.took()

        #self.dump_stats()
