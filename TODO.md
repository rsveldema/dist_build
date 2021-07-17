# Todos

- add benchmarks
- when seeing a compile error that an include couldn't be found, let the job-syncer auto-patch the ~/dist_build/config.json to add the missing include path
    - after patching the config.json we could re-upload the headers and restart the compile-job
- compiler command-line translation:
    - let a linux worker translate visual-studio-cl.exe command-lines to gcc-cross-compilation command lines. This should allow cheaper/simpler linux VMs in the cloud to act as workers for a windows dev machine.
- the sandbox holding the includes needs to be post/prefixed with a user-name to allow multiple users to share the same workers
- automated testing using github devops
- create a script to analyze CMakeLists.txt to auto-configure the include paths in ~/dist_build/config.json
- a dashboard
- put the daemon and syncer in containers
- run compiles on the build machines inside (windows) containers
- setup script to re-generate the certificates
- linux setup script to install the daemon as a systemd daemon
- windows setup script to install the daemon as a windows service
- OSx support
- performance optimizations for uploads/downloads
- wait for all uploads to header files to finish before starting a build
