
export MSYS_NO_PATHCONV=1

../../dist_build.sh gcc \
      -c \
      hello.c -o build/hello.o

../../dist_build.sh gcc \
      build/hello.o -o build/hello.out
