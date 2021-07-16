
export MSYS_NO_PATHCONV=1

./ms_dist_build.cmd /Program\ Files\ \(x86\)/Microsoft\ Visual\ Studio/2019/Community/VC/Tools/MSVC/14.29.30037/bin/Hostx64/x64/cl.exe \
      /I "/Program Files (x86)/Windows Kits/10/Include/10.0.19041.0/ucrt" \
      /I "/Program Files (x86)/Microsoft Visual Studio/2019/Community/VC/Tools/MSVC/14.29.30037/include" \
      /c \
     /Fo"build/" /EHsc \
      tests/hello.c


# cl /W4 /EHsc hello.cpp there.obj

echo "now linking it"

/c/Program\ Files\ \(x86\)/Microsoft\ Visual\ Studio/2019/Community/VC/Tools/MSVC/14.29.30037/bin/Hostx64/x64/cl.exe \
    /EHsc \
      build\\hello.obj /o build\\hello.exe /link /VERSION:3.14
