
set DBUILD_ROOT=%HOME%/source/repos/include_syncer/dist_build


set PYTHONPATH=%DBUILD_ROOT%:$PYTHONPATH


set PATH=%PATH%;c:\Python38

python -m dist_build.dist_build  %*
