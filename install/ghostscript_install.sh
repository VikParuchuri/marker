#!/bin/bash

wget https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10012/ghostscript-10.01.2.tar.gz
tar -xvf ghostscript-10.01.2.tar.gz
cd ghostscript-10.01.2
./configure
sudo make install
cd ..
sudo rm -rf ghostscript-10.01.2
rm ghostscript-10.01.2.tar.gz