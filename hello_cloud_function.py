#!/usr/bin/env python

import base64
import google.auth
import json
# import os

from google.cloud import secretmanager
from googleapiclient.discovery import build

SHEET_ID = '144uxVvgsrSfbgS5lIbFzCfu52-mFVdXX67KjodH-uL0'
RANGE= 'Sheet1!A1:B4'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
YNAB_API_SECRET = 'projects/ynab-sheets-001/secrets/ynab-api/versions/latest'

def hello_pubsub(event, context):
    """Triggered from a message on a Cloud Pub/Sub topic.
    Args:
         event (dict): Event payload.
         context (google.cloud.functions.Context): Metadata for the event.
    """
    pubsub_message = base64.b64decode(event['data']).decode('utf-8')
    print(f'message: {pubsub_message}')
    # print(f'SHEET_ID: {os.environ.get("SHEET_ID")}')
    # what does next line do outside of cloud environment?
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

if __name__ == '__main__':
    hello_pubsub({'data': base64.b64encode(b'Hello command line')}, None)


# Local Variables:
# compile-command: "python hello_cloud_function.py"
# End:
