
rm -rf build
mkdir build


mkdir -p ~/dist_build
cp example_config.json ~/dist_build/config.json

export COMPLEXITY=100

python create_demo.cc.py $COMPLEXITY aaa > generated_aaa.h
python create_demo.cc.py $COMPLEXITY bbb > generated_bbb.h
python create_demo.cc.py $COMPLEXITY ccc > generated_ccc.h
python create_demo.cc.py $COMPLEXITY ddd > generated_ddd.h
python create_demo.cc.py $COMPLEXITY foo > generated_foo.h
python create_demo.cc.py $COMPLEXITY bar > generated_bar.h

(
    cd build
    export VERBOSE=1
    cmake .. -DCMAKE_TOOLCHAIN_FILE=dist_build_toolchain.cmake -GNinja 
    #cmake ..  -GNinja 
)

(
    cd build
    time cmake --build . -j
)