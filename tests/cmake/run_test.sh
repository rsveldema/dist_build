
rm -rf build
mkdir build


(
    cd build
    export VERBOSE=1
    cmake .. -DCMAKE_PROJ_DIR=`pwd`/../ -DCMAKE_TOOLCHAIN_FILE=dist_build_toolchain.cmake -GNinja 
    #cmake ..  -GNinja 
)

(
    cd build
    cmake --build  .
)