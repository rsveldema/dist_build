import json

def copy_over(dir: str):
    pass


fp = open('config.json')
data = json.loads(fp.read())
fp.close()


for cdir in data.dirs:
    copy_over(cdir)