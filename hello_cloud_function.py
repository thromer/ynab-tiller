#!/usr/bin/env python

import base64
import google.auth
import json

from google.cloud import secretmanager
from googleapiclient.discovery import build

SHEET_ID = '144uxVvgsrSfbgS5lIbFzCfu52-mFVdXX67KjodH-uL0'
RANGE= 'Sheet1!A1:B4'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
YNAB_API_SECRET = 'projects/ynab-sheets-001/secrets/ynab-api/versions/latest'

def hello_pubsub(*unused):
    creds, _ = google.auth.default(scopes=SCOPES)

    service = build('sheets', 'v4', credentials=creds)
    values = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range=RANGE,
        valueRenderOption='UNFORMATTED_VALUE').execute().get('values', [])
    print(f'values: {values}')

    # TODO stash it in local file system!!!
    # Grab YNAB API key from Secret Manager
    secret_manager_client = secretmanager.SecretManagerServiceClient()
    secret = secret_manager_client.access_secret_version(
        request={'name': YNAB_API_SECRET}).payload.data.decode()
    api_key = json.loads(secret)['api_key']
    print('got secret')

if __name__ == '__main__':
    hello_pubsub(None, None)

# Local Variables:
# compile-command: "python hello_cloud_function.py"
# End:
