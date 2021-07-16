# Todos

- when seeing a compile error that an include couldn't be found, let the job-syncer auto-patch the ~/dist_build/config.json to add the missing include path
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
