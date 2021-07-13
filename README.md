# Distributed builds

## Features

- Syncs whole include dirs between machines
- Detects changes to dirs and broadcast new header files or changes to header files
- python
    -> pyinstaller
- https instead of tcp (more security!)
- job-queue on coordinator

## Usage

Run this in a terminal on the machine you're doing development on:

```bash
    python syncer.py
```

On your development machine, instead of calling cl.exe directly, prefix it with dist_build like so:

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


## Installation:

pip install -r requirements.txt 

Next adapt the config.json to add your include dirs (in the config.json on the development machine) and prefered number of cores to use (on the build machines).

### Virtual environments

Because dist_build is written in python, it can be challenging to use in virtual environments.
We therefore can optionally run the dist_build script wrapped in an executable to workaround this.

To do so, execute the 'generate_dist_build_executable.sh' script.


### Security

We, by default, use SSL/TLS for communication between daemon <--> sync <---> dist_build programs.
The certificates are in src/certs and can be regenerated using the gen_self_signed_certs.sh script there.

