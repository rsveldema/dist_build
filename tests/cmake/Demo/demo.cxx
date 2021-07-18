#include "hello.h"

#include <iostream>

#include "../generated_bar.cc"

int main()
{
    if (foo())
    {
        std::cout << "foo ok" << std::endl;
    }

    return 0;
}