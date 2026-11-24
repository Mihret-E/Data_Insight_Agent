
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "insight.db"

with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            CBE_REGION,
            SUM(CAST(NO_OF_TXN AS REAL)) AS TOTAL_DIGITAL_TXN
        FROM W_BRANCH_TXN_SUMMARY_F_3
        WHERE CHANNAL_TYPE = 'DIGITAL TXN'
        GROUP BY CBE_REGION
        ORDER BY TOTAL_DIGITAL_TXN DESC
    """)

    print("\nDigital transactions by region:")
    for row in cursor.fetchall():
        print(row)

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "insight.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    SELECT
        CHANNAL_TYPE,
        COUNT(*) AS RECORD_COUNT,
        SUM(CAST(NO_OF_TXN AS REAL)) AS TOTAL_TXN_VOLUME
    FROM W_BRANCH_TXN_SUMMARY_F_3
    GROUP BY CHANNAL_TYPE
""")

print("\nTransaction volume by channel:")
print("-" * 60)

for row in cursor.fetchall():
    print(row)

conn.close() 