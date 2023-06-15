# TODO error handling

import json
import os.path
import ynab_api

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pprint import pprint
from ynab_api.apis.tags import transactions_api

# If modifying these scopes, delete the file $HOME/ynab-tiller-token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# The ID and range of a sample spreadsheet.
SPREADSHEET_ID = '1UQQgW3kBfxNBB50q1pg4Hn2c6DvwoKVUF_9GelZ1k1Q'
RANGE_NAME = 'Brokerage!A:G'

HOME_DIR = os.environ['HOME']
TOKEN_FILE = HOME_DIR + '/ynab-tiller-token.json'
CREDENTIALS_FILE = HOME_DIR + '/client_secret_503586827022-4det1688u753c66bgkplrn1eseno78bq.apps.googleusercontent.com.json'
YNAB_SECRETS_FILE = HOME_DIR + '/ynab-secrets.json'
YNAB_BUDGET_ID = 'de4c0d69-c96c-4f1d-833b-cb0b7151b364'
YNAB_BROKERAGE_ACCOUNT_ID = '93132634-e507-4c48-909d-981aef2cc70e'

def get_ynab_transactions_api():
    with open(YNAB_SECRETS_FILE) as f:
        secrets = json.load(f)
        api_key = secrets['api_key']
    
    configuration = ynab_api.Configuration(
        host="https://api.youneedabudget.com/v1")
    configuration.api_key['bearer'] = api_key
    configuration.api_key_prefix['bearer'] = 'Bearer'
    return transactions_api.TransactionsApi(ynab_api.ApiClient(configuration))

def get_spreadsheets_api():
    sheets_creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(TOKEN_FILE):
        sheets_creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not sheets_creds or not sheets_creds.valid:
        if sheets_creds and sheets_creds.expired and sheets_creds.refresh_token:
            sheets_creds.refresh(Requset())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES)
            sheets_creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(TOKEN_FILE, 'w') as token:
            token.write(sheets_creds.to_json())

    service = build('sheets', 'v4', credentials=sheets_creds)
    return service.spreadsheets()

def main():
    ynab = get_ynab_transactions_api()
    # spreadsheets = get_spreadsheets_api()
    
    # result = spreadsheets.values().get(spreadsheetId=SPREADSHEET_ID,
    #                                    range=RANGE_NAME).execute()
    # values = result.get('values', [])
    # print('values: ', values)
    # if not values:
    #     print('No data found.')
    #     return
    
    # print('Name, Major:')
    # for row in values:
    #     # Print columns A and C, which correspond to indices 0 and 2.
    #     print('%s, %s' % (row[0], row[2]))

    api_response = ynab.get_transactions_by_account(
        path_params={
            'budget_id': YNAB_BUDGET_ID, 
            'account_id': YNAB_BROKERAGE_ACCOUNT_ID
        },
        query_params={
            'since_date':'2020-01-01'
        })
    pprint(api_response)
        

if __name__ == '__main__':
    main()
