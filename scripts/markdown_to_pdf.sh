#!/bin/bash
# This will convert a markdown file generated by marker back into a pdf
# This is an example of how to work with the markdown output

if [ $# -ne 2 ]; then
    echo "Usage: $0 <input.md> <output.pdf>"
    exit 1
fi

pandoc $1 -o $2 --pdf-engine=xelatex --include-in-header=header.tex