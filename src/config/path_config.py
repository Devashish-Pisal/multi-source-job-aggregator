from pathlib import Path



PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FOLDER_PATH = PROJECT_ROOT / "config"

# Folders
DATA_FOLDER_PATH = PROJECT_ROOT / "data"
LOGS_FOLDER_PATH = PROJECT_ROOT / "logs"
PROCESSED_FOLDER_PATH = DATA_FOLDER_PATH / "processed"
RAW_FOLDER_PATH = DATA_FOLDER_PATH / "raw"
DUPLICATES_FOLDER_PATH = DATA_FOLDER_PATH / "duplicates"

# Files
DATABASE_FILE_PATH = DATA_FOLDER_PATH / "database" / "app.db"