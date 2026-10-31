import pandas as pd
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent

# If this script is inside scripts/, use the parent project folder.
if ROOT.name == "scripts":
    ROOT = ROOT.parent

DATA_DIR = ROOT / "data"
ORIGINAL = DATA_DIR / "training_data.csv"
NEW_DATA = DATA_DIR / "edupulse_english_2000_cleaned.csv"
OUTPUT = DATA_DIR / "training_data_merged_preview.csv"
BACKUP = DATA_DIR / "training_data_before_english_merge.csv"

required = {"language", "text", "sentiment"}

if not ORIGINAL.exists():
    raise FileNotFoundError(f"Missing file: {ORIGINAL}")

if not NEW_DATA.exists():
    raise FileNotFoundError(
        f"Missing file: {NEW_DATA}\n"
        "Place the downloaded CSV inside the data folder."
    )

original = pd.read_csv(ORIGINAL)
new = pd.read_csv(NEW_DATA)

for name, frame in [("Original", original), ("New", new)]:
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{name} dataset is missing columns: {missing}")

# Keep only the required columns from the new synthetic dataset.
new = new[["language", "text", "sentiment"]].copy()

# Validate the new dataset.
new["language"] = new["language"].astype(str).str.strip()
new["text"] = new["text"].astype(str).str.strip()
new["sentiment"] = new["sentiment"].astype(str).str.strip().str.capitalize()

new = new[
    new["language"].str.lower().eq("english")
    & new["text"].ne("")
    & new["sentiment"].isin(["Positive", "Negative", "Neutral"])
].copy()

# Make a preview only. Do not overwrite the original dataset.
combined = pd.concat([original, new], ignore_index=True, sort=False)

combined["_dedup_key"] = (
    combined["language"].astype(str).str.lower().str.strip()
    + "||"
    + combined["text"].astype(str).str.lower().str.replace(
        r"\s+", " ", regex=True
    ).str.strip()
)

before_dedup = len(combined)
combined = combined.drop_duplicates(
    subset="_dedup_key", keep="first"
).drop(columns="_dedup_key")

# Preserve the original file as a backup.
if not BACKUP.exists():
    shutil.copy2(ORIGINAL, BACKUP)

combined.to_csv(OUTPUT, index=False, encoding="utf-8")

print("Original rows:", len(original))
print("Valid new English rows:", len(new))
print("Duplicates removed:", before_dedup - len(combined))
print("Preview rows:", len(combined))
print("Preview saved to:", OUTPUT)
print("Original dataset remains unchanged.")