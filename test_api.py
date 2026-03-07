import requests
import json

base_url = "http://localhost:8000" # Assuming default, but let's check .env if needed

def test_positions():
    try:
        response = requests.get(f"{base_url}/positions/?limit=10")
        if response.status_code == 200:
            data = response.json()
            # Find a hiring.cafe job
            hc_jobs = [j for j in data if j.get('source') == 'hiring.cafe']
            print(f"Total jobs: {len(data)}")
            print(f"Hiring Cafe jobs in sample: {len(hc_jobs)}")
            if hc_jobs:
                print("Hiring Cafe Sample:")
                print(json.dumps(hc_jobs[0], indent=2))
            else:
                print("No Hiring Cafe jobs in first 10. Fetching more...")
                response = requests.get(f"{base_url}/positions/?limit=100")
                data = response.json()
                hc_jobs = [j for j in data if j.get('source') == 'hiring.cafe']
                if hc_jobs:
                    print(f"Found Hiring Cafe job in first 100: {hc_jobs[0]['title']}")
                    print(json.dumps(hc_jobs[0], indent=2))
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    test_positions()
