# utils/aws_cache/aws_s3.py

import boto3
import json
import os
import math
from datetime import datetime
from dotenv import load_dotenv


# --------------------------------------------------
# Load environment variables
# --------------------------------------------------

load_dotenv()

BUCKET = os.getenv("S3_BUCKET")
REGION = os.getenv("AWS_REGION")


# --------------------------------------------------
# Create S3 client
# boto3 automatically reads AWS keys from env
# --------------------------------------------------

s3 = boto3.client(
    "s3",
    region_name=REGION
)


# --------------------------------------------------
# Helper: Build S3 path
# --------------------------------------------------

def build_path(domain: str, field: str, topic: str) -> str:
    return f"{domain}/{field}/{topic}/papers.json"


# --------------------------------------------------
# Load leaf node
# --------------------------------------------------

def load_leaf(domain: str, field: str, topic: str) -> dict:

    path = build_path(domain, field, topic)

    try:
        obj = s3.get_object(
            Bucket=BUCKET,
            Key=path
        )

        data = json.loads(obj["Body"].read())

    except s3.exceptions.NoSuchKey:

        # If leaf doesn't exist, create empty
        data = {"papers": []}

        save_leaf(domain, field, topic, data)

    return data


# --------------------------------------------------
# Save leaf node
# --------------------------------------------------

def save_leaf(domain: str, field: str, topic: str, data: dict):

    path = build_path(domain, field, topic)

    s3.put_object(
        Bucket=BUCKET,
        Key=path,
        Body=json.dumps(data, indent=2)
    )


# --------------------------------------------------
# Paper scoring function
# --------------------------------------------------

def compute_paper_score(
        impact_factor: float,
        acceptance_rate: float,
        citations: int,
        year: int
):

    current_year = datetime.now().year

    delta_t = current_year - year

    prestige = impact_factor / (1 + acceptance_rate)

    citation_score = math.log(1 + citations)

    recency = 1 / (1 + 0.1 * delta_t)

    score = prestige * citation_score * recency

    return score


# --------------------------------------------------
# Insert paper into leaf (max 10 rule)
# --------------------------------------------------

def insert_paper(domain: str, field: str, topic: str, paper: dict):

    leaf = load_leaf(domain, field, topic)

    papers = leaf["papers"]

    if len(papers) < 10:

        papers.append(paper)

    else:

        worst_paper = min(papers, key=lambda x: x["score"])

        if paper["score"] > worst_paper["score"]:

            papers.remove(worst_paper)

            papers.append(paper)

    save_leaf(domain, field, topic, leaf)


# --------------------------------------------------
# Check if paper exists
# --------------------------------------------------

def paper_exists(domain: str, field: str, topic: str, doi: str):

    leaf = load_leaf(domain, field, topic)

    for p in leaf["papers"]:

        if p.get("doi") == doi:
            return True

    return False