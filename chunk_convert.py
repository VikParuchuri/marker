import argparse
import subprocess


def main():
    parser = argparse.ArgumentParser(description="Convert a folder of PDFs to a folder of markdown files in chunks.")
    parser.add_argument("in_folder", help="Input folder with pdfs.")
    parser.add_argument("out_folder", help="Output folder")
    args = parser.parse_args()

    # Construct the command
    cmd = f"./chunk_convert.sh {args.in_folder} {args.out_folder}"

    # Execute the shell script
    subprocess.run(cmd, shell=True, check=True)


if __name__ == "__main__":
    main()