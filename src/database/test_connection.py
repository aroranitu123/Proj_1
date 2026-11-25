
import os
import pg8000
from dotenv import load_dotenv

load_dotenv()

try:
    conn = pg8000.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT current_database(), current_user;
    """)

    result = cursor.fetchone()

    print("Connection successful!")
    print("Database:", result[0])
    print("User:", result[1])

    cursor.close()
    conn.close()

except Exception as e:
    print("Connection failed:", e)
