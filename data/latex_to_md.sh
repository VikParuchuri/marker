#!/bin/bash

# List all .tex files in the latex folder
FILES=$(find latex -name "*.tex")

for f in $FILES
do
  echo "Processing $f file..."
  base_name=$(basename "$f" .tex)
  out_file="references/${base_name}.md"

 pandoc --wrap=none \
         --no-highlight \
         --strip-comments \
         --from=latex \
         --to=commonmark_x+pipe_tables \
         "$f" \
         -o "$out_file"
  # Replace non-breaking spaces
  sed -i .bak 's/ / /g' "$out_file"
  sed -i .bak 's/ / /g' "$out_file"
  sed -i .bak 's/ / /g' "$out_file"
  sed -i .bak 's/ / /g' "$out_file"
  sed -i.bak -E 's/`\\cite`//g; s/<[^>]*>//g; s/\{[^}]*\}//g; s/\\cite\{[^}]*\}//g' "$out_file"
    sed -i.bak -E '
    s/`\\cite`//g;   # Remove \cite commands inside backticks
    s/::: //g;       # Remove the leading ::: for content markers
    s/\[//g;         # Remove opening square bracket
    s/\]//g;         # Remove closing square bracket
  ' "$out_file"
  # Remove .bak file
  rm "$out_file.bak"
done

