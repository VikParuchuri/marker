import argparse
import os
import subprocess
import pkg_resources


def chunk_convert_cli():
    parser = argparse.ArgumentParser(description="Convert a folder of PDFs to a folder of markdown files in chunks.")
    parser.add_argument("in_folder", help="Input folder with pdfs.")
    parser.add_argument("out_folder", help="Output folder")
    args = parser.parse_args()

    cur_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(cur_dir, "chunk_convert.sh")

    # Construct the command
    cmd = f"{script_path} {args.in_folder} {args.out_folder}"

    # Execute the shell script
    subprocess.run(cmd, shell=True, check=True)