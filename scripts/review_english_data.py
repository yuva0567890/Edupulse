import pandas as pd
import re
from pathlib import Path

source = Path("data/edupulse_english_2000_cleaned.csv")
output = Path("data/english_sentences_to_review.csv")

df = pd.read_csv(source)

patterns = {
    "prompt": r"\bprompt\b",
    "slow": r"\bslow\b",
    "comfortable": r"\bcomfortable\b",
    "efficient": r"\befficient\b",
    "consistent": r"\bconsistent\b",
    "well maintained": r"\bwell maintained\b",
    "easy to use": r"\beasy to use\b",
    "grammar_suspect": r"\b(?:areas|facilities|routes|rooms|lectures|exits)\s+is\b",
    "awkward_college_manages": r"\bcollege manages\b",
    "awkward_department_discusses": r"\bdepartment discusses\b",
}

def find_issues(text):
    issues = [
        name for name, pattern in patterns.items()
        if re.search(pattern, str(text), flags=re.IGNORECASE)
    ]
    return ", ".join(issues)

df["review_reason"] = df["text"].apply(find_issues)
review = df[df["review_reason"] != ""].copy()
review["review_status"] = "PENDING"

review.to_csv(output, index=False, encoding="utf-8-sig")

print("Total dataset rows:", len(df))
print("Sentences flagged for review:", len(review))
print("Review file:", output.resolve())
print("\nReview reasons:")
print(review["review_reason"].str.split(", ").explode().value_counts().to_string())
