import requests
import json

def test_urls():
    url = "http://localhost:8000/api/positions/?limit=100"
    try:
        r = requests.get(url)
        print(f"Status Code: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            hc_jobs = [j for j in data if 'hiring' in j.get('source', '').lower()]
            print(f"Total jobs: {len(data)}")
            print(f"Hiring Cafe jobs: {len(hc_jobs)}")
            for j in hc_jobs[:10]:
                print(f"Title: {j.get('title')}")
                print(f"  Source: {j.get('source')}")
                print(f"  Job URL: {j.get('job_url')}")
                print(f"  UID: {j.get('source_uid')}")
                print("-" * 20)
        else:
            print(r.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_urls()
