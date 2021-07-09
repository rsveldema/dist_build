
export MSYS_NO_PATHCONV=1

./dist_build.sh gcc \
      -c \
      tests/hello.c -o build/hello.o
