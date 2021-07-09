
export DBUILD_ROOT=$HOME/source/repos/include_syncer/dist_build


export PYTHONPATH=$DBUILD_ROOT:$PYTHONPATH

python -m dist_build.dist_build $@
