
import sys


class DistBuildOptions:
    _verbose: bool

    def __init__(self):
        self._verbose = False

        for arg in sys.argv[1:]:
            if arg == "-v":
                self._verbose = True
            else:
                print("unknown argument: " + arg)

    def verbose(self) -> bool:
        return self._verbose
