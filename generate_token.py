from google_auth_oauthlib.flow import InstalledAppFlow
import pickle

SCOPES = ['https://www.googleapis.com/auth/drive']

flow = InstalledAppFlow.from_client_secrets_file(
    'oauth_client_secret.json',
    SCOPES
)

creds = flow.run_local_server(port=0)

# Save token
with open('token.json', 'w') as token:
    token.write(creds.to_json())

print("token.json created successfully")