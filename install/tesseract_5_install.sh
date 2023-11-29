#!/bin/bash

sudo apt-get install apt-transport-https
echo "deb https://notesalexp.org/tesseract-ocr5/$(lsb_release -cs)/ $(lsb_release -cs) main" \
| sudo tee /etc/apt/sources.list.d/notesalexp.list > /dev/null
sudo apt-get update -oAcquire::AllowInsecureRepositories=true
sudo apt-get install notesalexp-keyring -oAcquire::AllowInsecureRepositories=true
sudo apt-get update
sudo apt-get install tesseract-ocr
