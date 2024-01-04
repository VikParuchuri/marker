#!/bin/bash

GS_VERSION="10.01.2"

wget https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10012/ghostscript-$GS_VERSION.tar.gz
tar -xvf ghostscript-$GS_VERSION.tar.gz
cd ghostscript-$GS_VERSION
./configure

if [[ $EUID -ne 0 ]]; then
    sudo make install
else
    make install
fi

cd ..
rm -rf ghostscript-$GS_VERSION
rm -f ghostscript-$GS_VERSION.tar.gz
