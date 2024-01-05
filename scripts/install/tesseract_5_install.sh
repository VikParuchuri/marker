#!/bin/bash

install_debian() {
sudo apt-get install apt-transport-https
echo "deb https://notesalexp.org/tesseract-ocr5/$(lsb_release -cs)/ $(lsb_release -cs) main" \
| sudo tee /etc/apt/sources.list.d/notesalexp.list > /dev/null
sudo apt-get update -oAcquire::AllowInsecureRepositories=true
sudo apt-get install notesalexp-keyring -oAcquire::AllowInsecureRepositories=true
sudo apt-get update
sudo apt-get install tesseract-ocr
}

install_fedora() {
  echo "Automatic install not implemented yet on this distribution (Fedora)"
}

install_arch() {
  echo "Automatic install not implemented yet on this distribution (Arch Linux)"
}

install_mac() {
  echo "Automatic install not implemented yet on this distribution (macOS)"
}

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        case $ID in
            debian|ubuntu|linuxmint)
                install_debian
                ;;
            fedora)
                install_fedora
                ;;
            arch|manjaro)
                install_arch
                ;;
            *)
                echo "Unsupported Linux distribution: $ID"
                exit 1
                ;;
        esac
    else
        echo "Cannot determine the Linux distribution"
        exit 1
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    install_mac
else
    echo "Unsupported Operating System: $OSTYPE"
    exit 1
fi
