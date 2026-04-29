import urllib.request
import urllib.error
import json

try:
    req = urllib.request.Request("http://127.0.0.1:8000/positions/paginated?page=1&page_size=10")
    with urllib.request.urlopen(req) as response:
        print("Success:", response.read().decode())
except urllib.error.HTTPError as e:
    print(f"HTTPError: {e.code}")
    print("Body:", e.read().decode())
except Exception as e:
    print(f"Exception: {e}")
