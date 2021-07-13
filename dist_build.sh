
export DBUILD_ROOT=$HOME/source/repos/dist_build/src


export PYTHONPATH=$DBUILD_ROOT:$PYTHONPATH

python -m src.dist_build $@
