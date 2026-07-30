from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FINAL_DATA_DIR = BASE_DIR / 'data'

DATASET_PATH = FINAL_DATA_DIR / 'faq_saeb.json'