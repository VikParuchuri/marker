import argparse
import subprocess
import pkg_resources


def main():
    parser = argparse.ArgumentParser(description="Convert a folder of PDFs to a folder of markdown files in chunks.")
    parser.add_argument("in_folder", help="Input folder with pdfs.")
    parser.add_argument("out_folder", help="Output folder")
    args = parser.parse_args()

    script_path = pkg_resources.resource_filename(__name__, 'chunk_convert.sh')

    # Construct the command
    cmd = f"{script_path} {args.in_folder} {args.out_folder}"

    # Execute the shell script
    subprocess.run(cmd, shell=True, check=True)


if __name__ == "__main__":
    main()