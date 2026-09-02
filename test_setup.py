from dotenv import load_dotenv
import os

load_dotenv()
message = os.getenv("MY_TEST_MESSAGE")
print("Your environment is working. Message from .env file:", message)