import json
import argparse


def verify_scores(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)

    marker_score = data["marker"]["average_score"]
    if marker_score < 90:
        raise ValueError("Marker score below 90")


def verify_table_scores(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)

    avg = sum([r["marker_score"] for r in data["marker"]]) / len(data)
    if avg < 0.7:
        raise ValueError("Average score is below the required threshold of 0.7")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify benchmark scores")
    parser.add_argument("file_path", type=str, help="Path to the json file")
    parser.add_argument("--type", type=str, help="Type of file to verify", default="marker")
    args = parser.parse_args()
    if args.type == "marker":
        verify_scores(args.file_path)
    elif args.type == "table":
        verify_table_scores(args.file_path)
