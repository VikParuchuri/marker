# Use an official Python 3.9+ image as a parent image, based on Debian for compatibility with your instructions
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    # Add system requirements for tesseract and ghostscript here as needed
    # Assume scripts/install/*.sh are modified to be non-interactive and do not require sudo
    && rm -rf /var/lib/apt/lists/*

# Clone the repo
RUN git clone https://github.com/VikParuchuri/marker.git . \
    && scripts/install/tesseract_5_install.sh \
    && scripts/install/ghostscript_install.sh \
    && cat scripts/install/apt-requirements.txt | xargs apt-get install -y

# Install Poetry
RUN pip install poetry

# Install Python dependencies via Poetry
RUN poetry install

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
# RUN poetry run pip uninstall -y torch && poetry run pip install torch=={desired_version}

# The command to run when the container starts
# This CMD line is a placeholder; adjust it based on how you want to use the container
CMD ["poetry", "run", "python", "convert_single.py", "/path/to/file.pdf", "/path/to/output.md", "--parallel_factor", "2", "--max_pages", "10"]
