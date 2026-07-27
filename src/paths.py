from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_DIR = PROJECT_ROOT / "database"
OUTPUT_DIR = PROJECT_ROOT / "output"

RAW_DATA_FILE = DATA_DIR / "raw_expenses.csv"
CLEAN_DATA_FILE = DATA_DIR / "cleaned_expenses.csv"
CLEANING_REPORT_FILE = OUTPUT_DIR / "cleaning_report.json"
CATEGORY_SUMMARY_FILE = OUTPUT_DIR / "category_summary.csv"
MONTHLY_SUMMARY_FILE = OUTPUT_DIR / "monthly_summary.csv"
STATISTICS_JSON_FILE = OUTPUT_DIR / "statistics.json"
AI_ANALYSIS_FILE = OUTPUT_DIR / "ai_analysis.txt"
DATABASE_FILE = DATABASE_DIR / "expense_ai.db"
SCHEMA_FILE = DATABASE_DIR / "schema.sql"


def ensure_directories() -> None:
    for directory in (DATA_DIR, DATABASE_DIR, OUTPUT_DIR):
        directory.mkdir(parents=True, exist_ok=True)
