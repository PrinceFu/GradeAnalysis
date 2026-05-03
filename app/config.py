import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'data', 'scores.db')}"
CONVERSION_RULES_PATH = os.path.join(BASE_DIR, "data", "conversion_rules.json")

SECRET_KEY = os.environ.get("GRADE_SECRET_KEY", "jiangsu-gaokao-grade-analysis-2026")
