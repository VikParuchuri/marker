import json
import argparse


def verify_scores(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)

    multicolcnn_score = data["marker"]["files"]["multicolcnn.pdf"]["score"]
    switch_trans_score = data["marker"]["files"]["switch_trans.pdf"]["score"]

    if multicolcnn_score <= 0.34 or switch_trans_score <= 0.40:
        raise ValueError("One or more scores are below the required threshold of 0.4")


def verify_table_scores(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)

    avg = sum([r["score"] for r in data]) / len(data)
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
