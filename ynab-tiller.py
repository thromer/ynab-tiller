#!/usr/bin/env python3

# TODO error handling

import csv
import datetime
import json
import operator
import os.path
import re
import sys
import ynab_api

from collections import defaultdict
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pprint import pformat
from pprint import pprint
from ynab_api.api import transactions_api
from ynab_api.model.post_transactions_wrapper import PostTransactionsWrapper
from ynab_api.model.save_transaction import SaveTransaction

# If modifying these scopes, delete the file $HOME/ynab-tiller-token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# The ID and range of a sample spreadsheet.
SPREADSHEET_ID = '1UQQgW3kBfxNBB50q1pg4Hn2c6DvwoKVUF_9GelZ1k1Q'
RANGE_NAME = 'Brokerage_recent!A:G'

HOME_DIR = os.environ['HOME']
TOKEN_FILE = HOME_DIR + '/ynab-tiller-token.json'
CREDENTIALS_FILE = HOME_DIR + '/client_secret_503586827022-4det1688u753c66bgkplrn1eseno78bq.apps.googleusercontent.com.json'
YNAB_SECRETS_FILE = HOME_DIR + '/ynab-secrets.json'
YNAB_BUDGET_ID = 'de4c0d69-c96c-4f1d-833b-cb0b7151b364'
YNAB_BROKERAGE_ACCOUNT_ID = '93132634-e507-4c48-909d-981aef2cc70e'
YNAB_CHASE_AMAZON_ACCOUNT_ID = '46be1192-177d-480b-aa29-283fdd327c8a'

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
            sheets_creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES)
            sheets_creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(TOKEN_FILE, 'w') as token:
            token.write(sheets_creds.to_json())

    service = build('sheets', 'v4', credentials=sheets_creds)
    return service.spreadsheets()

EXCEL_EPOCH = datetime.date(1900, 1, 1).toordinal() - 2

def date_from_excel_date(sheet_date):
    return datetime.date.fromordinal(EXCEL_EPOCH + sheet_date)

def date_to_excel_date(python_date):
    return datetime.date.fromordinal(python_date.toordinal() - EXCEL_EPOCH).toordinal()

def filter_transaction(row):
    full_desc = row['Full Description']
    id = row['tiller_transaction_id']  # for debugging
    
    if full_desc == 'DIVIDEND RECEIVED FIDELITY GOVERNMENT MONEY MARKET':
        # interest on brokerage money market
        # print(f'allowing1 {id} "{full_desc}"')
        return False

    if re.match(r'^(?:PURCHASE INTO|REDEMPTION FROM) CORE ACCOUNT FIDELITY GOVERNMENT MONEY MARKET$', full_desc):
        # print(f'filtering1 {id} "{full_desc}"')
        return True

    # Too much work to list all the things to exclude, instead just rely on
    # rarity of the default fund changing from Fidelity Government Money Market.
    # if re.match(r'^REINVESTMENT (?:VANGUARD BD INDEX FDS TOTAL BND MRKT|FIDELITY GOVERNMENT MONEY MARKET)$', full_desc):
    #    # print(f'filtering2 {id} "{full_desc}"')
    #    return True
    # '^DIVIDEND RECEIVED .*(?:VANGUARD INTL EQUITY INDEX FDS|VANGUARD TOTAL STOCK MARKET INDEX|VANGUARD TOTAL INTERNATIONAL STOCK|VANGUARD BD INDEX FDS TOTAL BND' # Use that regex instead of the below
    # if full_desc == 'DIVIDEND RECEIVED VANGUARD BD INDEX FDS TOTAL BND MRKT':
    #    # print(f'filtering3 {id} "{full_desc}"')
    #    return True

    if re.match(r'^(?:DIVIDEND RECEIVED|REINVESTMENT) ', full_desc):
    #    # print(f'filtering2 {id} "{full_desc}"')
        return True
    
    # print(f'allowing2 {id} "{full_desc}"')
    return False
    
def make_transaction(ynab_account_id, row):
    if not ynab_account_id:
        raise "Must provide tiller_id"
    return {
        'account_id': ynab_account_id,
        'amount': round(row['Amount'] * 1000), 
        'date': date_from_excel_date(row['Date']),
        'import_id': row['tiller_transaction_id'],
        'payee_name': row['Description'][:50], # required on read but not write ?!
        'memo': row['Full Description'][:200]
    }

class Main:
    def __init__(self):
        self._ynab = get_ynab_transactions_api()
        self._spreadsheets = get_spreadsheets_api()

    def get_ynab_transactions(self):
        return self._ynab.get_transactions_by_account(
            YNAB_BUDGET_ID, 
            YNAB_BROKERAGE_ACCOUNT_ID,
            # YNAB_CHASE_AMAZON_ACCOUNT_ID,
            since_date=(datetime.date.today() - datetime.timedelta(90)).strftime('%Y-%m-%d')
        )['data']['transactions']

    def get_all_ynab_transactions(self):
        return self._ynab.get_transactions(
            YNAB_BUDGET_ID, 
            since_date=(datetime.date.today() - datetime.timedelta(90)).strftime('%Y-%m-%d')
        )['data']['transactions']

    def _update_ynab_internal(self):
        brokerage_values = self._spreadsheets.values().get(
            spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME,
            valueRenderOption='UNFORMATTED_VALUE').execute().get('values', [])

        if not brokerage_values:
            raise('Empty brokerage results.')

        brokerage_headers = brokerage_values[0]
        brokerage_entry_list = [
            defaultdict(str, { brokerage_headers[i] : row[i] for i in range(len(row)) })
            for row in brokerage_values[1:] 
        ]
        brokerage_entry_tiller_ids = set(
            [entry['tiller_transaction_id'] for entry in brokerage_entry_list])

        # print(brokerage_entry_tiller_ids)

        ynab_tiller_values = self._spreadsheets.values().get(
            spreadsheetId=SPREADSHEET_ID, range='ynab_tiller_recent!A:C',
            valueRenderOption='UNFORMATTED_VALUE').execute().get('values', [])

        if not ynab_tiller_values:
            raise('Empty ynab_tiller results.')

        ynab_tiller_headers = ynab_tiller_values[0]
        ynab_tiller_entry_list = [
            { ynab_tiller_headers[i] : row[i] for i in range(len(row)) }
            for row in ynab_tiller_values[1:] 
        ]
        ynab_tiller_entry_tiller_ids = set(
            [entry['tiller_transaction_id'] for entry in ynab_tiller_entry_list])

        # print(ynab_tiller_entry_tiller_ids)

        new_tiller_ids = brokerage_entry_tiller_ids.difference(ynab_tiller_entry_tiller_ids)
        print('new_tiller_ids', new_tiller_ids)

        ynab_transactions = []
        # This is a bit confusing. It is looking at what is known to tiller,
        # and filtering by new_tiller_ids, which is what is not known to YNAB.
        for entry in brokerage_entry_list:
            # print(entry['tiller_transaction_id'])
            if entry['tiller_transaction_id'] not in new_tiller_ids:
                # print(f"skipping existing id {entry['tiller_transaction_id']}")
                # print(f"skip1 {entry['tiller_transaction_id']}")
                continue
            if filter_transaction(entry):
                # print(f"skip2 {entry['tiller_transaction_id']}")
                continue
            ynab_transaction = make_transaction(YNAB_BROKERAGE_ACCOUNT_ID, entry)
            print(ynab_transaction)
            ynab_transactions.append(SaveTransaction(**ynab_transaction))

        # Yuck! Assumes nothing interesting will happen after this point
        if not ynab_transactions:
            # print('ynab_transactions empty, nothing to do')
            return
        
        api_response = self._ynab.create_transaction(
            YNAB_BUDGET_ID,
            PostTransactionsWrapper(transactions=ynab_transactions)
        )
        pprint(api_response)
        ynab_data = api_response['data']
        return ynab_data

    def _apply_tiller_ynab_sheet_updates(self, new_sheets_row_maps):
        print('THROMER _apply_tiller_ynab_sheet_updates')
        pprint(new_sheets_row_maps)
        result = self._spreadsheets.values().get(
            spreadsheetId=SPREADSHEET_ID, range='ynab_tiller!1:1',
            valueRenderOption='UNFORMATTED_VALUE').execute()

        values = result.get('values', [])
        if not values:
            raise('Empty results.')
        values = result.get('values', [])
        if not values:
            raise('Empty results.')
        headers = values[0]
        header_index = {i : headers[i] for i in range(len(headers))}
        new_sheets_row_lists = [ [row[header_index[i]] for i in range(len(headers))] for row in new_sheets_row_maps ]
        append_response = self._spreadsheets.values().append(
            spreadsheetId=SPREADSHEET_ID, 
            range='ynab_tiller!A:C',
            body={
                'range': 'ynab_tiller!A:C',
                'values': new_sheets_row_lists
            },
            valueInputOption='RAW',
            responseValueRenderOption='UNFORMATTED_VALUE'
        ).execute()
        
    def _update_tiller_ynab_sheet(self, transactions):
        # Append tiller_id + ynab_id + date to sheets
        self._apply_tiller_ynab_sheet_updates([
            self._tiller_ynab_sheet_row_map(transaction)
            for transaction in transactions ])

    def _tiller_ynab_sheet_row_map(self, ynab_transaction):
        return {
            'tiller_transaction_id': ynab_transaction['import_id'],
            'ynab_transaction_id': ynab_transaction['id'],
            'date': date_to_excel_date(ynab_transaction['date'])
        } 

    def _recover_from_duplicate_import_ids(self, import_ids):
        print('THROMER _recover_from_duplicate_import_ids')
        import_ids = set(import_ids)
        transactions = self.get_ynab_transactions()
        candidates = [self._tiller_ynab_sheet_row_map(t) for t in transactions if t['import_id'] in import_ids]
        print('candidates', pformat(candidates))
        deleted_candidates = [self._tiller_ynab_sheet_row_map(t) for t in transactions if (t['import_id'] in import_ids and t['deleted'])]
        print('skipping deleted', pformat(deleted_candidates))

        self._apply_tiller_ynab_sheet_updates([ 
            self._tiller_ynab_sheet_row_map(transaction)
            for transaction in transactions
            if (transaction['import_id'] in import_ids and
                not transaction['deleted']) ])

    def update_ynab(self):
        print('THROMER update_ynab')
        ynab_data = self._update_ynab_internal()
    
        if ynab_data and ynab_data['duplicate_import_ids']:
            print('THROMER uh oh duplicates 1')
            # This could happen if we update YNAB but fail to note it in Sheets.
            self._recover_from_duplicate_import_ids(ynab_data['duplicate_import_ids'])
            ynab_data = self._update_ynab_internal()
            if ynab_data and ynab_data['duplicate_import_ids']:
                print('THROMER uh oh duplicates 2')
                for id in ynab_data['duplicate_import_ids']:
                    print(id, file=sys.stderr)
                raise Exception('Uh oh, unexpected duplicate import_ids even after repair ' + str(ynab_data['duplicate_import_ids']))

        if ynab_data:
            self._update_tiller_ynab_sheet(ynab_data['transactions'])

 
def none_blank(s):
    return "" if s == None else s

def main():
    m = Main()

    if False:
        result = [
            {
                'tiller_transaction_id': none_blank(t['import_id']),
                'ynab_transaction_id': str(t['id']),
	        'date': str(date_to_excel_date(t['date'])),
                'Amount': f"{(round(t['amount']/1000.0, 2)):.2f}",
                'Account': none_blank(t['account_name']),
                'Category': none_blank(t['category_name']),
                'Description': none_blank(t['payee_name'])
            } for t in m.get_ynab_transactions()]

        dw = csv.DictWriter(sys.stdout, [
            'tiller_transaction_id', 
            'ynab_transaction_id',
	    'date',
	    'Amount',
            'Account',
            'Category',
            'Description'
        ], extrasaction='ignore')

        dw.writeheader()
        for row in sorted(result, key=operator.itemgetter('tiller_transaction_id')):
            dw.writerow(row)
        return

    if False:
        pprint(m.get_all_ynab_transactions())
        return

    if False:
        print('Buyer beware, not very robust to duplicates AFAICT', file=sys.stderr)
        # Seems like if we import once, approve everything that matched, and
        # redo import it is ok, but that's no fun at all.
        #
        # Oh I hope it is I because I had those garbage columns breaking stuff?
        sys.exit(1)

    if True:
        m.update_ynab()
    
    if False:
        pprint(m.get_ynab_transactions())

if __name__ == '__main__':
    main()

# Local Variables:
# compile-command: "python ynab-tiller.py"
# End:    
