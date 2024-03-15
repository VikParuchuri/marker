# Use an official Python 3.9+ image as a parent image, based on Debian for compatibility with your instructions
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the current directory contents into the container at /usr/src/app
COPY . .

# Make the scripts executable
RUN chmod +x scripts/install/tesseract_5_install.sh \
    && chmod +x scripts/install/ghostscript_install.sh


RUN apt-get update && apt-get install -y apt-transport-https \
    && . /etc/os-release \
    && echo "deb https://notesalexp.org/tesseract-ocr5/${VERSION_CODENAME} ${VERSION_CODENAME} main" > /etc/apt/sources.list.d/notesalexp.list \
    && apt-get update -oAcquire::AllowInsecureRepositories=true \
    && apt-get install -y notesalexp-keyring -oAcquire::AllowInsecureRepositories=true --allow-unauthenticated \
    && apt-get update \
    && apt-get install gcc python3-dev -y \
    && apt-get install -y tesseract-ocr \
    # Install additional requirements from apt-requirements.txt
    && apt-get install -y $(cat scripts/install/apt-requirements.txt | xargs)  \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install poetry \
    && poetry config virtualenvs.create false \
    && poetry install

# Set up environment variables
# Replace these with your actual paths or configuration
ENV TESSDATA_PREFIX=/usr/local/share/tessdata
ENV TORCH_DEVICE=cpu
# For GPU setup, adjust the TORCH_DEVICE accordingly, e.g., cuda or mps
# And ensure INFERENCE_RAM is set based on your GPU's VRAM
# ENV INFERENCE_RAM=16
# Additional environment variables can be set here or passed at runtime

# Copy everything else into the container
COPY . .

# Update pytorch - adjust for GPU or CPU
# CPU only example, uncomment and adjust as necessary
RUN poetry run pip uninstall -y torch && poetry run pip install torch

# The command to run when the container starts
# This CMD line is a placeholder; adjust it based on how you want to use the container
CMD ["poetry", "run", "python", "convert_single.py", "0.0.0.0", "5000", "./", "--parallel_factor", "2", "--max_pages", "10"]
