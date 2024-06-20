import json
import argparse


def verify_scores(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)

    multicolcnn_score = data["marker"]["files"]["multicolcnn.pdf"]["score"]
    switch_trans_score = data["marker"]["files"]["switch_trans.pdf"]["score"]

    if multicolcnn_score <= 0.39 or switch_trans_score <= 0.4:
        raise ValueError("One or more scores are below the required threshold of 0.4")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify benchmark scores")
    parser.add_argument("file_path", type=str, help="Path to the json file")
    args = parser.parse_args()
    verify_scores(args.file_path)
