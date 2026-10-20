#######################This code reads your Excel files and 
#creates two database tables in insight.db.######################################


from pathlib import Path
import sqlite3
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "insight.db"

EXCEL_FILES = {
    "W_ACCOUNT_INFOR_F": DATA_DIR / "W_ACCOUNT_INFOR_F.xlsx",
    "W_BRANCH_TXN_SUMMARY_F_3": DATA_DIR / "W_BRANCH_TXN_SUMMARY_F_3.xlsx",
    "W_COMPANY_D": DATA_DIR / "W_COMPANY_D.xlsx",
}


def import_excel():
    with sqlite3.connect(DB_PATH) as conn:
        for table_name, file_path in EXCEL_FILES.items():
            if not file_path.exists():
                raise FileNotFoundError(
                    f"File not found: {file_path}"
                )

            df = pd.read_excel(file_path)

            # Clean column names for easier SQL querying
            df.columns = [
                str(col).strip().upper().replace(" ", "_")
                for col in df.columns
            ]

            df.to_sql(
                table_name,
                conn,
                if_exists="replace",
                index=False
            )

            print(f"\nImported table: {table_name}")
            print(f"Rows: {len(df)}")
            print(f"Columns: {df.columns.tolist()}")

    print(f"\nDatabase created at: {DB_PATH}")


if __name__ == "__main__":
    import_excel()



#######################This version imports all
# three Excel files without pandas or NumPy..######################################


from pathlib import Path
import sqlite3
import re
from datetime import date, datetime
from openpyxl import load_workbook

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "insight.db"

EXCEL_FILES = {
    "W_ACCOUNT_INFOR_F": "W_ACCOUNT_INFOR_F.xlsx",
    "W_BRANCH_TXN_SUMMARY_F_3": "W_BRANCH_TXN_SUMMARY_F_3.xlsx",
    "W_COMPANY_D": "W_COMPANY_D.xlsx",
}


def clean_name(name):
    name = str(name).strip().upper()
    name = re.sub(r"\W+", "_", name)
    return name.strip("_")


def convert_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def import_excel():
    with sqlite3.connect(DB_PATH) as conn:
        for table_name, filename in EXCEL_FILES.items():
            file_path = DATA_DIR / filename

            if not file_path.exists():
                raise FileNotFoundError(
                    f"Excel file not found: {file_path}"
                )

            workbook = load_workbook(
                file_path, read_only=True, data_only=True
            )
            sheet = workbook.active
            rows = sheet.iter_rows(values_only=True)

            headers = next(rows, None)
            if not headers:
                workbook.close()
                raise ValueError(f"No header row in {filename}")

            columns = [clean_name(c) for c in headers]

            if any(not c for c in columns):
                workbook.close()
                raise ValueError(
                    f"Blank column name in {filename}"
                )

            if len(columns) != len(set(columns)):
                workbook.close()
                raise ValueError(
                    f"Duplicate column names in {filename}"
                )

            quoted_columns = [
                '"' + c.replace('"', '""') + '"'
                for c in columns
            ]

            conn.execute(
                f'DROP TABLE IF EXISTS "{table_name}"'
            )

            conn.execute(
                f'CREATE TABLE "{table_name}" '
                f'({", ".join(c + " TEXT" for c in quoted_columns)})'
            )

            placeholders = ", ".join("?" for _ in columns)
            insert_sql = (
                f'INSERT INTO "{table_name}" '
                f'({", ".join(quoted_columns)}) '
                f'VALUES ({placeholders})'
            )

            count = 0
            for row in rows:
                if all(value is None for value in row):
                    continue

                values = [
                    convert_value(value) for value in row
                ]
                conn.execute(insert_sql, values)
                count += 1

            workbook.close()
            print(f"Imported {table_name}: {count} rows")
            print("Columns:", columns)

    print(f"\nDatabase created: {DB_PATH}")


if __name__ == "__main__":
    import_excel()


##### to verify the db has been created


from pathlib import Path
import sqlite3

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "insight.db"

with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()

    tables = [
        "W_ACCOUNT_INFOR_F",
        "W_BRANCH_TXN_SUMMARY_F_3",
        "W_COMPANY_D",
    ]

    for table in tables:
        print(f"\n{'=' * 50}")
        print(f"TABLE: {table}")

        cursor.execute(f'PRAGMA table_info("{table}")')
        columns = [row[1] for row in cursor.fetchall()]
        print("Columns:", columns)

        cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
        print("Total rows:", cursor.fetchone()[0])

        cursor.execute(f'SELECT * FROM "{table}" LIMIT 3')
        rows = cursor.fetchall()

        for row in rows:
            print(row)

#/****We will test whether CO_CODE in the account table 
#matches BRANCHCODE in the branch dimension, and whether 
#branch names match between the tables.**/


from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).resolve().parent.parent / "insight.db"

with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()

    # Check account codes against branch codes
    print("\n1. ACCOUNT CODE TO BRANCH CODE")

    cursor.execute("""
        SELECT
            a.CO_CODE,
            b.BRANCHCODE,
            b.BRANCHNAME
        FROM W_ACCOUNT_INFOR_F a
        LEFT JOIN W_COMPANY_D b
            ON TRIM(a.CO_CODE) = TRIM(b.BRANCHCODE)
    """)

    for row in cursor.fetchall():
        print(row)

    # Check branch names between transaction and branch tables
    print("\n2. TRANSACTION BRANCH NAME MATCHES")

    cursor.execute("""
        SELECT
            t.BRANCHNAME,
            b.BRANCHNAME,
            b.BRANCHCODE
        FROM W_BRANCH_TXN_SUMMARY_F_3 t
        LEFT JOIN W_COMPANY_D b
            ON UPPER(TRIM(t.BRANCHNAME))
             = UPPER(TRIM(b.BRANCHNAME))
    """)

    for row in cursor.fetchall():
        print(row)


##Investigate the join keys

from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).resolve().parent.parent / "insight.db"

with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()

    checks = {
        "ACCOUNT TABLE - CODES AND BRANCH NAMES": """
            SELECT CO_CODE, BRANCHNAME, DISTRICTNAME, CBE_REGION
            FROM W_ACCOUNT_INFOR_F
        """,
        "BRANCH DIMENSION - CODES AND NAMES": """
            SELECT BRANCHCODE, BRANCHNAME, OLDNAME, OLD_DISTRICTNAME
            FROM W_COMPANY_D
        """,
        "TRANSACTION TABLE - BRANCH AND REGION": """
            SELECT BRANCHNAME, DISTRICTNAME, CBE_REGION
            FROM W_BRANCH_TXN_SUMMARY_F_3
        """
    }

    for title, query in checks.items():
        print(f"\n{'=' * 60}")
        print(title)
        cursor.execute(query)

        for row in cursor.fetchall():
            print(row)


#Let’s begin with a simpler task that requires only one table.
# This lets us validate the database
# and SQL results before introducing the LLM.

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
