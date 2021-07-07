# Distributed builds

## Usage

- Machine 1:

```bash
    python daemon.py 
```

- Machine 2, terminal 1:

```bash
    python syncer.py
```

- Machine 2, terminal 2:

```bash
    
python dist_build.py /Program\ Files\ \(x86\)/Microsoft\ Visual\ Studio/2019/Community/VC/Tools/MSVC/14.29.30037/bin/Hostx64/x64/cl.exe \
      /I /Program\ Files\ \(x86\)/Windows\ Kits/10/Include/10.0.19041.0/ucrt \
      /I /Program\ Files\ \(x86\)/Microsoft\ Visual\ Studio/2019/Community/VC/Tools/MSVC/14.29.30037/include \
      /c \
     /Fo"build/" /EHsc \
      tests/hello.c
```


## Features

- Syncs whole include dirs between machines
- Detects changes to dirs and broadcast new header files or changes to header files
- python
- https instead of tcp (more security!)
- job-queue on coordinator

## Installation:

pip install -r requirements.txt 

