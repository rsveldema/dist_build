# CMakeLists files in this project can
# refer to the root source directory of the project as ${HELLO_SOURCE_DIR} and
# to the root binary directory of the project as ${HELLO_BINARY_DIR}.
cmake_minimum_required (VERSION 3.10)
project (HELLO CXX)

message("CURRENT PROJ SOURCE DIR ${CMAKE_SOURCE_DIR}")

set(CMAKE_C_COMPILER_LAUNCHER ${PROJECT_SOURCE_DIR}/../../ms_dist_build.cmd CACHE STRING "")
set(CMAKE_CXX_COMPILER_LAUNCHER ${PROJECT_SOURCE_DIR}/../../ms_dist_build.cmd CACHE STRING "")

# Recurse into the "Hello" and "Demo" subdirectories. This does not actually
# cause another cmake executable to run. The same process will walk through
# the project's entire directory structure.
add_subdirectory (Hello)
add_subdirectory (Demo)
