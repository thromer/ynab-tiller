#!/usr/bin/env python

import base64
import google.auth
import os

from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def hello_pubsub(event, context):
    """Triggered from a message on a Cloud Pub/Sub topic.
    Args:
         event (dict): Event payload.
         context (google.cloud.functions.Context): Metadata for the event.
    """
    pubsub_message = base64.b64decode(event['data']).decode('utf-8')
    print(f'message: {pubsub_message}')
    print(f'SHEET_ID: {os.environ.get("SHEET_ID")}')
    # what does next line do outside of cloud environment?
    creds, _ = google.auth.default(scopes=SCOPES)

    service = build('sheets', 'v4', credentials=creds)

if __name__ == '__main__':
    hello_pubsub({'data': base64.b64encode(b'Hello command line')}, None)
