
rm -rf build
mkdir build


mkdir -p ~/dist_build
cp example_config.json ~/dist_build/config.json

(
    cd build
    export VERBOSE=1
    cmake .. -DCMAKE_TOOLCHAIN_FILE=dist_build_toolchain.cmake -GNinja 
    #cmake ..  -GNinja 
)

(
    cd build
    cmake --build  .
)