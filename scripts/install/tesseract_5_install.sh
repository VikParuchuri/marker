#!/bin/bash

## Check if the script is running as root
if [[ $EUID -ne 0 ]]; then
    exec sudo /bin/bash "$0" "$@"
fi

apt-get install apt-transport-https lsb-release -y
echo "deb https://notesalexp.org/tesseract-ocr5/$(lsb_release -cs)/ $(lsb_release -cs) main" \
| tee /etc/apt/sources.list.d/notesalexp.list > /dev/null
apt-get update -oAcquire::AllowInsecureRepositories=true
apt-get install notesalexp-keyring -oAcquire::AllowInsecureRepositories=true -y
apt-get update
apt-get install tesseract-ocr -y
