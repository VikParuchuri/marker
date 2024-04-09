#!/bin/bash

# Check if the correct number of arguments is provided
if [ "$#" -lt 2 ]; then
    echo "Usage: docker run -v /path/to/input:/input -v /path/to/output:/output -v /path/to/cache:/app/.cache image_name [COMMAND] [ARGS]"
    echo ""
    echo "Commands:"
    echo "  single /input/file.pdf /output/file.md [OPTIONS]"
    echo "    Convert a single file"
    echo "    Usage: docker run -v /path/to/input:/input -v /path/to/output:/output -v /path/to/cache:/app/.cache image_name single /input/file.pdf /output/file.md [--parallel_factor N] [--max_pages N]"
    echo "    Options:"
    echo "      --parallel_factor N  Increase batch size and parallel OCR workers by N (default: 1)"
    echo "      --max_pages N        Maximum number of pages to process (default: all)"
    echo ""
    echo "  multi /input /output [OPTIONS]"
    echo "    Convert multiple files"
    echo "    Usage: docker run -v /path/to/input:/input -v /path/to/output:/output -v /path/to/cache:/app/.cache image_name multi /input /output [--workers N] [--max N] [--metadata_file FILE] [--min_length N]"
    echo "    Options:"
    echo "      --workers N           Number of PDFs to convert in parallel (default: 1)"
    echo "      --max N               Maximum number of PDFs to convert (default: all)"
    echo "      --metadata_file FILE  Path to JSON file with per-PDF metadata (default: none)"
    echo "      --min_length N        Minimum number of characters to extract before processing (default: 0)"
    exit 1
fi

# Get the command
COMMAND=$1
shift

# Activate the poetry shell
poetry shell

# Run the specified command with the provided arguments
case $COMMAND in
  single)
    # Check if the correct number of arguments is provided
    if [ "$#" -lt 2 ]; then
      echo "Usage: docker run -v /path/to/input:/input -v /path/to/output:/output -v /path/to/cache:/app/.cache image_name single /input/file.pdf /output/file.md [--parallel_factor N] [--max_pages N]"
      exit 1
    fi

    # Set the input file and output file from the arguments
    INPUT_FILE=$1
    OUTPUT_FILE=$2
    shift 2

    # Run the convert_single.py script with the provided arguments
    poetry run python /app/convert_single.py "$INPUT_FILE" "$OUTPUT_FILE" "$@"
    ;;

  multi)
    # Check if the correct number of arguments is provided 
    if [ "$#" -lt 2 ]; then
      echo "Usage: docker run -v /path/to/input:/input -v /path/to/output:/output -v /path/to/cache:/app/.cache image_name multi /input /output [--workers N] [--max N] [--metadata_file FILE] [--min_length N]"
      exit 1
    fi

    # Set the input and output directories from the arguments
    INPUT_DIR=$1
    OUTPUT_DIR=$2
    shift 2

    # Run the convert.py script with the provided arguments
    poetry run python /app/convert.py "$INPUT_DIR" "$OUTPUT_DIR" "$@"
    ;;

  *)
    echo "Unknown command: $COMMAND"
    exit 1
    ;;
esac
