
from pathlib import Path
import sqlite3
import json
import urllib.request
import re
import matplotlib.pyplot as plt

# Locate the project and database
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "insight.db"

# Read the database schema
def get_database_schema():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)

        schema = []
        for (table_name,) in cursor.fetchall():
            cursor.execute(f'PRAGMA table_info("{table_name}")')
            columns = cursor.fetchall()
            column_names = [column[1] for column in columns]
            schema.append(
                f"Table: {table_name}\n"
                f"Columns: {', '.join(column_names)}"
            )

    return "\n\n".join(schema)


def validate_data_availability(question):
    """
    Check whether the sample database contains the data
    required to answer the business question.
    """

    question_lower = question.lower()

    with sqlite3.connect(
        f"file:{DB_PATH.as_posix()}?mode=ro",
        uri=True
    ) as conn:

        cursor = conn.cursor()

        # Check digital vs non-digital comparison
        if (
            "non-digital" in question_lower
            or "non digital" in question_lower
        ):
            cursor.execute("""
                SELECT COUNT(*)
                FROM W_BRANCH_TXN_SUMMARY_F_3
                WHERE CHANNAL_TYPE IS NOT NULL
                  AND CHANNAL_TYPE != 'DIGITAL TXN'
            """)

            non_digital_count = cursor.fetchone()[0]

            if non_digital_count == 0:
                return (
                    "Insufficient data: The available dataset "
                    "contains no non-digital transaction records. "
                    "A digital vs. non-digital comparison cannot "
                    "currently be performed."
                )

        # Check geographical account analysis
        if (
            "account" in question_lower
            and any(word in question_lower for word in
                    ["region", "district", "branch"])
        ):
            geo_columns = {
                "region": "CBE_REGION",
                "district": "DISTRICTNAME",
                "branch": "BRANCHNAME"
            }

            for keyword, column in geo_columns.items():
                if keyword in question_lower:
                    cursor.execute(f"""
                        SELECT COUNT(*)
                        FROM W_ACCOUNT_INFOR_F
                        WHERE {column} IS NOT NULL
                    """)

                    populated_count = cursor.fetchone()[0]

                    if populated_count == 0:
                        return (
                            f"Insufficient data: The {column} "
                            "column in W_ACCOUNT_INFOR_F contains "
                            "no populated values. Account analysis "
                            f"by {keyword} is currently unavailable."
                        )

    return None


def calculate_percentages(columns, rows):
    """
    Calculate each row's percentage contribution.
    """

    if not rows or len(columns) < 2:
        return []

    try:
        values = [float(row[-1]) for row in rows]
        total = sum(values)

        if total == 0:
            return []

        return [
            round((value / total) * 100, 2)
            for value in values
        ]

    except (ValueError, TypeError):
        return []


def calculate_period_change(rows):
    """
    Calculate percentage change between consecutive periods.
    Assumes the first column contains dates and the
    last column contains numeric values.
    """

    if len(rows) < 2:
        return []

    changes = []

    try:
        for i in range(1, len(rows)):
            previous = float(rows[i - 1][-1])
            current = float(rows[i][-1])

            if previous == 0:
                change = None
            else:
                change = round(
                    ((current - previous) / previous) * 100,
                    2
                )

            changes.append({
                "period": str(rows[i][0]),
                "previous_value": previous,
                "current_value": current,
                "percentage_change": change
            })

        return changes

    except (ValueError, TypeError):
        return []


def interpret_results(question, columns, rows):
    """
    Generate descriptive business insights using SQL results
    and Python-verified percentage calculations.
    """

    if not rows:
        return "No data is available to generate business insights."

    # Format SQL results
    results_text = "\n".join(
        " | ".join(str(value) for value in row)
        for row in rows
    )

    # Calculate percentage contributions
    percentages = calculate_percentages(columns, rows)

    percentage_text = "Not calculated"

    if percentages:
        percentage_text = "\n".join(
            f"{row[0]}: {percentage}%"
            for row, percentage in zip(rows, percentages)
        )

    # Calculate verified period-over-period changes
    period_changes = calculate_period_change(rows)

    period_change_text = "Not calculated or insufficient data"

    if period_changes:
        verified_changes = []

        for change in period_changes:
            percentage_change = change["percentage_change"]

            if percentage_change is not None:
                direction = (
                    "increase" if percentage_change > 0
                    else "decrease" if percentage_change < 0
                    else "no change"
                )

                verified_changes.append(
                    f"{change['period']}: "
                    f"{abs(percentage_change)}% {direction} "
                    f"(from {change['previous_value']} "
                    f"to {change['current_value']})"
                )

        if verified_changes:
            period_change_text = "\n".join(verified_changes)

    # Build the LLM prompt
    prompt = f"""
You are a banking data analyst.

Business Question:
{question}

Result Columns:
{", ".join(columns)}

Query Results:
{results_text}

VERIFIED PERCENTAGE CONTRIBUTIONS:
{percentage_text}

VERIFIED PERIOD-OVER-PERIOD CHANGES:
{period_change_text}

IMPORTANT RULES:
1. Percentage contribution represents a share of the total.
2. Period-over-period change represents the percentage increase or
   decrease between consecutive periods.
3. Never confuse percentage contribution with period-over-period change.
4. Do not calculate or estimate percentages yourself.
5. Use only the verified Python calculations provided above.
6. If a calculation is unavailable, do not invent or estimate it.
7. Never describe a percentage contribution as a daily, monthly,
   or yearly increase or decrease.

INSTRUCTIONS:
1. Explain the main findings in clear business language.
2. Identify the highest and lowest values where applicable.
3. Report verified percentage contributions where relevant.
4. Report verified period-over-period changes where relevant.
5. Do not invent explanations, causes, or recommendations.
6. Do not speculate about population or customer behavior.
7. Mention data limitations where relevant.
8. Keep the explanation concise and descriptive.

Provide a short business insight.
"""

    payload = {
        "model": "qwen2.5:3b",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 384
        }
    }

    request = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.loads(response.read().decode("utf-8"))

    return result["message"]["content"].strip()


def generate_chart(columns, rows, question):
    """
    Generate a chart based on the business question.
    Supports bar, line, and pie charts.
    """

    if not rows or len(columns) < 2:
        print("\nNot enough data to generate a chart.")
        return

    try:
        labels = [str(row[0]) for row in rows]
        values = [float(row[-1]) for row in rows]

        question_lower = question.lower()

        plt.figure(figsize=(10, 6))

        # Select chart type
        if any(word in question_lower for word in [
            "trend", "over time", "daily", "monthly",
            "quarterly", "yearly"
        ]):
            chart_type = "line"

            plt.plot(
                labels,
                values,
                marker="o",
                linewidth=2.5,
                color="#7051A3"
            )

            plt.fill_between(
                range(len(values)),
                values,
                color="#7051A3",
                alpha=0.12
            )

            plt.ylabel(columns[-1])

        elif any(word in question_lower for word in [
            "percentage", "proportion", "share",
            "contribution", "composition"
        ]):
            chart_type = "pie"

            plt.pie(
                values,
                labels=labels,
                autopct="%1.1f%%",
                startangle=90,
                colors=[
                    "#7051A3",
                    "#D4AF37",
                    "#A58BCB",
                    "#E6D28A",
                    "#C7B5DE"
                ]
            )

            plt.axis("equal")

        else:
            chart_type = "bar"

            bars = plt.bar(
                labels,
                values,
                color="#7051A3",
                edgecolor="#D4AF37",
                linewidth=1.5
            )

            for bar in bars:
                height = bar.get_height()

                plt.text(
                    bar.get_x() + bar.get_width() / 2,
                    height,
                    f"{height:,.0f}",
                    ha="center",
                    va="bottom"
                )

            plt.ylabel(columns[-1])

        plt.title(
            question,
            fontsize=14,
            fontweight="bold"
        )

        if chart_type != "pie":
            plt.xlabel(columns[0])
            plt.xticks(rotation=30, ha="right")
            plt.grid(axis="y", linestyle="--", alpha=0.3)
            plt.gca().set_axisbelow(True)

        plt.tight_layout()

        chart_path = BASE_DIR / "regional_transaction_chart.png"

        plt.savefig(
            chart_path,
            dpi=300,
            bbox_inches="tight",
            facecolor="white"
        )

        plt.show()
        plt.close()

        print(f"\nChart type: {chart_type}")
        print(f"Chart saved successfully: {chart_path}")

    except (ValueError, TypeError, IndexError) as error:
        print(f"\nChart generation error: {error}")


# Ask the user a business question
question = input("Enter your business question: ")
# Validate data availability before generating SQL
validation_message = validate_data_availability(question)

if validation_message:
    print("\nData Availability Check:")
    print("-" * 50)
    print(validation_message)
    print("\nQuery generation stopped.")
    exit()

schema = get_database_schema()



prompt = f"""
You are a SQLite SQL generator for a banking data analysis assistant.

Database schema:
{schema}

Business question:
{question}

TABLE SELECTION RULES:
1. Account questions must use W_ACCOUNT_INFOR_F.
2. Transaction questions must use W_BRANCH_TXN_SUMMARY_F_3.
3. Branch information questions must use W_COMPANY_D.
4. Use only the table or tables necessary to answer the question.
5. Do not join tables unless information from multiple tables is genuinely required.
6. Never join tables using columns without a verified matching relationship.

ACCOUNT RULES:
7. Use ACTIVE for active accounts.
8. Use INACTIVE for inactive accounts.
9. Use NO_TOTAL_ACCOUNT for total accounts.
10. Account geographical fields are currently NULL in the sample data.
11. Do not generate regional, district, or branch account reports from NULL fields.

TRANSACTION RULES:
12. Use SUM(CAST(NO_OF_TXN AS REAL)) for transaction volume.
13. Use CHANNAL_TYPE = 'DIGITAL TXN' for digital transactions.
14. Use CBE_REGION for regional transaction analysis.
15. Use DISTRICTNAME for district transaction analysis.
16. Use BRANCHNAME for branch transaction analysis.
17. Group by the appropriate geographical column when requested.

GENERAL RULES:
18. For questions asking for results by region, GROUP BY CBE_REGION only.
19. For questions asking for results by district, GROUP BY DISTRICTNAME only.
20. For questions asking for results by branch, GROUP BY BRANCHNAME only.
21. Never add additional geographical grouping columns unless the user explicitly requests them.
22. Do not add IS NOT NULL filters unless the user explicitly requests exclusion of missing values or the analysis requires it.
23. For district-level analysis, return one row per district.
24. For branch-level analysis, return one row per branch.p

"""



# Request SQL from Ollama
payload = {
    "model": "qwen2.5:3b",
    "messages": [
        {"role": "user", "content": prompt}
    ],
    "stream": False,
    "options": {
        "temperature": 0,
        "num_predict": 512
    }
}

request = urllib.request.Request(
    "http://localhost:11434/api/chat",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST"
)

try:
    print("\nAsking Qwen2.5 to generate SQL...")

    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.loads(response.read().decode("utf-8"))

# Extract SQL from the LLM response
    llm_response = result["message"]["content"].strip()

    print("\nDEBUG - Raw LLM Response:")
    print("------------------------------")
    print(repr(llm_response))
    print("------------------------------")

# Extract SQL from Markdown code fences
    code_match = re.search(
        r"```(?:sql)?\s*(.*?)```",
        llm_response,
        flags=re.IGNORECASE | re.DOTALL
    )

    if code_match:
        sql = code_match.group(1).strip()
    else:
        raise ValueError("No SQL query found in the LLM response.")

# Normalize SQL
    sql = sql.rstrip(";").strip() + ";"

# Apply a trusted SQL template for digital transaction volume by district
    question_lower = question.lower()

    if (
        "digital" in question_lower
        and "transaction" in question_lower
        and "district" in question_lower
    ):

        print("\nDistrict-level digital transaction question detected.")

        sql = """
        SELECT
            DISTRICTNAME,
            SUM(CAST(NO_OF_TXN AS REAL)) AS TOTAL_DIGITAL_TXN_VOLUME
        FROM W_BRANCH_TXN_SUMMARY_F_3
        WHERE CHANNAL_TYPE = 'DIGITAL TXN'
        GROUP BY DISTRICTNAME
        ORDER BY TOTAL_DIGITAL_TXN_VOLUME DESC;
        """
    

# Daily digital transaction trend
    if (
        "digital" in question_lower
        and "transaction" in question_lower
        and any(word in question_lower for word in [
            "daily", "trend", "over time"
        ])
    ):
        print("\nDaily trend question detected. Using trusted SQL.")

        sql = """
        SELECT
            BUSINESS_DATE,
            SUM(CAST(NO_OF_TXN AS REAL)) AS DIGITAL_TXN_VOLUME
        FROM W_BRANCH_TXN_SUMMARY_F_3
        WHERE CHANNAL_TYPE = 'DIGITAL TXN'
        GROUP BY BUSINESS_DATE
        ORDER BY BUSINESS_DATE;
        """


    # Apply a trusted SQL template for digital transaction volume by branch
    if (
        "digital" in question_lower
        and "transaction" in question_lower
        and "branch" in question_lower
    ):
        print("\nBranch-level digital transaction question detected.")

        sql = """
        SELECT
            BRANCHNAME,
            SUM(CAST(NO_OF_TXN AS REAL)) AS TOTAL_DIGITAL_TXN_VOLUME
        FROM W_BRANCH_TXN_SUMMARY_F_3
        WHERE CHANNAL_TYPE = 'DIGITAL TXN'
        GROUP BY BRANCHNAME
        ORDER BY TOTAL_DIGITAL_TXN_VOLUME DESC;
        """
        # Apply a trusted SQL template for digital transaction types
    if (
        "digital" in question_lower
        and "transaction" in question_lower
        and ("type" in question_lower or "types" in question_lower)
    ):
        print("\nDigital transaction type question detected.")

        sql = """
        SELECT
            TXN_TYPE AS DIGITAL_TRANSACTION_TYPE,
            SUM(CAST(NO_OF_TXN AS REAL)) AS TRANSACTION_VOLUME
        FROM W_BRANCH_TXN_SUMMARY_F_3
        WHERE CHANNAL_TYPE = 'DIGITAL TXN'
        GROUP BY TXN_TYPE
        ORDER BY TRANSACTION_VOLUME DESC;
        """

# Route account questions to a trusted SQL template
    question_lower = question.lower()

    if (
        "account" in question_lower
        and "active" in question_lower
        and "inactive" in question_lower
    ):
        print("\nAccount question detected. Using the account data table.")

        sql = """
        SELECT
            SUM(CAST(ACTIVE AS REAL)) AS TOTAL_ACTIVE_ACCOUNTS,
            SUM(CAST(INACTIVE AS REAL)) AS TOTAL_INACTIVE_ACCOUNTS
        FROM W_ACCOUNT_INFOR_F
        """


    # Remove optional Markdown code fences
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s*```$", "", sql).strip()
    sql = sql.rstrip(";").strip() + ";"

    print("\nGenerated SQL:")
    print("-" * 50)
    print(sql)

    # Allow only a single read-only SELECT statement
    if not re.match(r"^SELECT\b", sql, flags=re.IGNORECASE):
        raise ValueError("Rejected: only SELECT queries are allowed.")

    if ";" in sql[:-1]:
        raise ValueError("Rejected: multiple SQL statements are not allowed.")

    if re.search(
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|"
        r"ATTACH|DETACH|PRAGMA|VACUUM)\b",
        sql,
        flags=re.IGNORECASE
    ):
        raise ValueError("Rejected: potentially unsafe SQL detected.")

    # Execute the query against the existing database
    print("\nQuery Results:")
    print("-" * 50)

    with sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True) as conn:
        cursor = conn.cursor()
        cursor.execute(sql)

        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()

        print(" | ".join(columns))
        print("-" * 50)

        if not rows:
            print("No results found.")
        else:
            for row in rows:
                print(" | ".join(str(value) for value in row))

            print(f"\nTotal rows: {len(rows)}")

        # Calculate percentage contribution
        percentages = calculate_percentages(columns, rows)

        if percentages:
            print("\nPERCENTAGE CONTRIBUTION")
            print("-" * 50)

        for row, percentage in zip(rows, percentages):
            print(f"{row[0]}: {percentage}%")

# Generate business insights from query results
        print("\nGenerating business insights...")

        insight = interpret_results(question, columns, rows)

        print("\nBUSINESS INSIGHTS")
        print("=" * 50)
        print(insight)

        # Generate chart from SQL results
        print("\nGenerating business chart...")

        generate_chart(columns, rows, question)

except Exception as error:
    print(f"\nError: {error}")
