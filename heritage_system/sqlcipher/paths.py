from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_DIR = BASE_DIR


def get_app_dir() -> Path:
    return Path(os.environ.get('HERITAGE_APP_DIR', str(PROJECT_DIR))).resolve()


def get_data_dir() -> Path:
    return Path(os.environ.get('HERITAGE_DATA_DIR', str(get_app_dir() / 'data'))).resolve()


def get_config_dir() -> Path:
    return Path(os.environ.get('HERITAGE_CONFIG_DIR', str(get_app_dir() / 'config'))).resolve()


def get_backup_dir() -> Path:
    return Path(os.environ.get('HERITAGE_BACKUP_DIR', str(get_app_dir() / 'backup'))).resolve()


def get_database_path() -> Path:
    return Path(os.environ.get('HERITAGE_DB_FILE', str(get_data_dir() / 'database.db'))).resolve()


def ensure_runtime_directories() -> None:
    for directory in (get_data_dir(), get_config_dir(), get_backup_dir()):
        directory.mkdir(parents=True, exist_ok=True)
