# Todos

## Flexibility TODOs

- when seeing a compile error that an include couldn't be found, let the job-syncer auto-patch the ~/dist_build/config.json to add the missing include path
    - after patching the config.json we could re-upload the headers and restart the compile-job
- compiler command-line translation:
    - let a linux worker translate visual-studio-cl.exe command-lines to gcc-cross-compilation command lines. This should allow cheaper/simpler linux VMs in the cloud to act as workers for a windows dev machine.
- create a script to analyze CMakeLists.txt to auto-configure the include paths in ~/dist_build/config.json
- a dashboard
- OSx support
- wait for all uploads to header files to finish before starting a build
- when uploading includes we can ignore certain directories:
        def is_ignorable_dir(item):
  Currently the names are hardcoded instead of fetching them from config.json
- the worker currently needs to know the addresses of the syncers. 
  We can remove this runtime dependency by letting the syners register themselves (with a lease?) with the workers.
  This way the workers don't really need much configuration at all anymore.


## Performance TODOs

- if syncer runs on the same machine as dist_build.exe, let the syner write the obj/.d files instead of forwarding them to the dist_build.exe process and doing it there?
- performance optimizations for uploads/downloads
- add benchmarks
- use asyncio for writing the obj and .d files too

## Infrastructure TODOs

- put the worker and syncer in docker containers
- run compiles on the build machines inside (windows) containers
- setup script to re-generate the certificates
- linux setup script to install the worker as a systemd service
- windows setup script to install the worker as a windows service


## Testing TODOs
- add unit tests
- add integration tests
- setup automated testing
- automated testing using github devops


