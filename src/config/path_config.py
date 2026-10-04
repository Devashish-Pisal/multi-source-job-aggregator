from pathlib import Path



PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Folders
DATA_FOLDER_PATH = PROJECT_ROOT / "data"
LOGS_FOLDER_PATH = PROJECT_ROOT / "logs"
RAW_FOLDER_PATH = DATA_FOLDER_PATH / "raw"
REJECTED_FOLDER_PATH = DATA_FOLDER_PATH / "rejected"
PROFILE_FOLDER_PATH = PROJECT_ROOT / "profile"

# Files
DATABASE_FILE_PATH = DATA_FOLDER_PATH / "database" / "app.db"
