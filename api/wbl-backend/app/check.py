import os

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

print("DB_HOST:", os.getenv('DB_HOST'))
print("DB_PORT:", os.getenv('DB_PORT'))
print("DB_USER:", os.getenv('DB_USER'))
print("DB_PASSWORD:", os.getenv('DB_PASSWORD'))
print("DB_NAME:", os.getenv('DB_NAME'))
