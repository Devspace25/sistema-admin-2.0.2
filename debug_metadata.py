
import sys
import os

sys.path.insert(0, os.getcwd())
from src.admin_app.models import Base

print("Tables in Base.metadata:")
for t in Base.metadata.tables:
    print(f" - {t}")
