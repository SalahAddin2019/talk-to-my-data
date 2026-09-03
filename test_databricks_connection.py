from dotenv import load_dotenv
import os
from databricks import sql

load_dotenv()

connection = sql.connect(
    server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"),
    http_path=os.getenv("DATABRICKS_HTTP_PATH"),
    access_token=os.getenv("DATABRICKS_TOKEN")
)

cursor = connection.cursor()
cursor.execute("SELECT COUNT(*) AS total_orders FROM tgs_talk_to_data.orders")
result = cursor.fetchall()

print("Connected successfully!")
print(result)

cursor.close()
connection.close()