
(
    cd src
    
    rm -rf ~/dist_build/bin
    mkdir -p ~/dist_build/bin

    pyinstaller --clean -y --onefile -F --distpath ~/dist_build/bin dist_build.py

    #cp -r dist/dist_build/* ~/dist_build/bin
    
    rm -rf dist build
)

