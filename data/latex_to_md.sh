#!/bin/bash

# List all .tex files in the latex folder
FILES=$(find latex -name "*.tex")

for f in $FILES
do
  echo "Processing $f file..."
  base_name=$(basename "$f" .tex)
  out_file="references/${base_name}.md"

  pandoc --wrap=none --no-highlight --strip-comments=true -s "$f" -t plain -o "$out_file"
  # Replace non-breaking spaces
  sed -i .bak 's/ / /g' "$out_file"
  sed -i .bak 's/ / /g' "$out_file"
  sed -i .bak 's/ / /g' "$out_file"
  sed -i .bak 's/ / /g' "$out_file"
  # Remove .bak file
  rm "$out_file.bak"
done

