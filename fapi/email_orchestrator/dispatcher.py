import requests
import logging
import json

logger = logging.getLogger(__name__)

class EmailDispatcher:
    def __init__(self, service_url: str):
        self.service_url = service_url

    def dispatch_job(self, payload: dict):
        """
        Calls the external Email Service via REST API.
        Expected API endpoint: POST /send
        """
        try:
            # Ensure the URL is correctly formatted
            url = f"{self.service_url.rstrip('/')}/send"
            
            logger.info(f"🚀 Dispatching job_run_id={payload.get('job_run_id')} to {url}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(url, json=payload, timeout=60)
            logger.info(f"📨 Service Response: HTTP {response.status_code}")
            response.raise_for_status()
            
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP Error calling email service at {self.service_url}: {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response content: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in EmailDispatcher: {e}")
            return None
