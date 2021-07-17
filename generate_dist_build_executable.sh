
(
    cd src
    
    pyinstaller --clean -y dist_build.py
    
    cp ./dist/dist_build/dist_build.exe ..

    rm -rf dist build
)

