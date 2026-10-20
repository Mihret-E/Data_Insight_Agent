
from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).resolve().parent.parent / "insight.db"

question = "Which digital transaction types have the highest transaction volume?"

query = """
    SELECT
        TXN_TYPE,
        SUM(CAST(NO_OF_TXN AS REAL)) AS TOTAL_TRANSACTIONS
    FROM W_BRANCH_TXN_SUMMARY_F_3
    WHERE UPPER(TRIM(CHANNAL_TYPE)) = 'DIGITAL TXN'
    GROUP BY TXN_TYPE
    ORDER BY TOTAL_TRANSACTIONS DESC
"""

with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()
    cursor.execute(query)
    results = cursor.fetchall()

print("Business Question:", question)
print("\nResults:")
print("-" * 50)

for transaction_type, total in results:
    print(f"{transaction_type}: {total:g} transactions")
