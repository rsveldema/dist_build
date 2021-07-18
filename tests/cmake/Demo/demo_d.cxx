 #include " hello.h"

#include <iostream>

#include "../generated_ddd.h"

int main()
{
    if (foo())
    {
        std::cout << "foo ok" << std::endl;
    }

    return 0;
}