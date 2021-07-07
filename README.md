# Distributed builds

## Usage

Run this in a terminal on the machine you're doing development on:

```bash
    python syncer.py
```

On your developmentn machine, instead of calling cl.exe directly, prefix it with dist_build like so:

```bash
    
python dist_build.py /Program\ Files\ \(x86\)/Microsoft\ Visual\ Studio/2019/Community/VC/Tools/MSVC/14.29.30037/bin/Hostx64/x64/cl.exe \
      /I /Program\ Files\ \(x86\)/Windows\ Kits/10/Include/10.0.19041.0/ucrt \
      /I /Program\ Files\ \(x86\)/Microsoft\ Visual\ Studio/2019/Community/VC/Tools/MSVC/14.29.30037/include \
      /c \
     /Fo"build/" /EHsc \
      tests/hello.c
```

On the build machines you use:

```bash
    python daemon.py 
```



## Features

- Syncs whole include dirs between machines
- Detects changes to dirs and broadcast new header files or changes to header files
- python
- https instead of tcp (more security!)
- job-queue on coordinator

## Installation:

pip install -r requirements.txt 

