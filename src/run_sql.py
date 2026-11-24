
import sqlite3

# Connect to your existing database
conn = sqlite3.connect("insight.db")
cursor = conn.cursor()

sql = """
SELECT
    TXN_TYPE,
    SUM(CAST(NO_OF_TXN AS REAL)) AS TOTAL_TRANSACTIONS
FROM W_BRANCH_TXN_SUMMARY_F_3
WHERE UPPER(TRIM(CHANNAL_TYPE)) = 'DIGITAL TXN'
  AND UPPER(TRIM(DIGITAL_TYPE)) = 'CBE BIRR'
GROUP BY TXN_TYPE
ORDER BY TOTAL_TRANSACTIONS DESC;
"""

cursor.execute(sql)

print("\nDigital transaction types by transaction count:")
print("-" * 50)

for row in cursor.fetchall():
    print(f"Transaction type: {row[0]} | Count: {row[1]}")

conn.close()
