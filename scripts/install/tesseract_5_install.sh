#!/bin/bash

# Functions to install Tesseract on Debian-based systems
# Will this function work on linux-mint, ubuntu and debian?
install_debian() {
sudo apt-get install apt-transport-https
echo "deb https://notesalexp.org/tesseract-ocr5/$(lsb_release -cs)/ $(lsb_release -cs) main" \
| sudo tee /etc/apt/sources.list.d/notesalexp.list > /dev/null
sudo apt-get update -oAcquire::AllowInsecureRepositories=true
sudo apt-get install notesalexp-keyring -oAcquire::AllowInsecureRepositories=true
sudo apt-get update
sudo apt-get install tesseract-ocr
}

# Functions to install Tesseract on Fedora-based systems
# DELETE THIS LINE WHEN YOU TEST THIS ON FEDORA. I DIDN'T!!!
install_fedora() {
  sudo dnf install tesseract
}

# Functions to install Tesseract on Arch-based systems
# Tested on Archlinux, Not Manjaro.
install_arch() {
  sudo pacman -S tesseract tesseract-data-eng
}

# Functions to install Tesseract on macOS
# DELETE THIS LINE WHEN YOU TEST THIS ON MAC. I DIDN'T!!!
install_mac() {
  if ! command -v brew &> /dev/null;
  then
    echo "Homebrew is not installed."
    read -r -p "Do you want to install Homebrew? (y/n) " choice

    case "$choice" in
      y|Y ) /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)";;
      n|N ) echo "Exiting. Please install Homebrew and re-run the script."
            exit 1;;
        * ) echo "Invalid choice. Exiting. Please install Homebrew and re-run the script."
            exit 1;;
      esac
  fi

  #install tesseract
  brew install tesseract
}

# Main "Function"
# Detecting the Operating System and calling the respective install function
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
