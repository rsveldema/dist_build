from os import getenv

def storage_dir():
    home = getenv("HOME")
    if home == None:
        home = "c:/"
    storage = home + '/dist_build'
    return storage



