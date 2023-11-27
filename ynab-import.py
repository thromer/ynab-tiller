# TODO error handling

import csv
import datetime
import json
import operator
import os.path
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
from ynab_api.api import accounts_api
from ynab_api.api import categories_api
from ynab_api.api import transactions_api
from ynab_api.model.post_transactions_wrapper import PostTransactionsWrapper
from ynab_api.model.save_transaction import SaveTransaction

# If modifying these scopes, delete the file $HOME/ynab-tiller-token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# The ID and range of a sample spreadsheet.
# SPREADSHEET_ID = '1UQQgW3kBfxNBB50q1pg4Hn2c6DvwoKVUF_9GelZ1k1Q'
TMP_SPREADSHEET_ID = '1oaROwwYjENAkJgDJiSJcLHPSyEP6jswNswzHQqV0va8'
RANGE_NAME = 'export_me!A:H'

HOME_DIR = os.environ['HOME']
TOKEN_FILE = HOME_DIR + '/ynab-tiller-token.json'
CREDENTIALS_FILE = HOME_DIR + '/client_secret_503586827022-4det1688u753c66bgkplrn1eseno78bq.apps.googleusercontent.com.json'
YNAB_SECRETS_FILE = HOME_DIR + '/ynab-secrets.json'
YNAB_BUDGET_ID = 'de4c0d69-c96c-4f1d-833b-cb0b7151b364'
YNAB_AMAZON_SPLIT_ACCOUNT_ID = 'e3479ea6-0acb-46d1-b084-7c7e4d982733'

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

class Main:
    def __init__(self):
        ynab_client = self._make_ynab_client()
        self._ynab_a = accounts_api.AccountsApi(ynab_client)
        self._ynab_t = transactions_api.TransactionsApi(ynab_client)
        self._spreadsheets = get_spreadsheets_api()
        self._ynab_account_name_id_map = self._get_ynab_account_name_id_map()
        self._categories = self.Categories(ynab_client)
        self._the_account_name = None

    class Categories:
        def __init__(self, ynab_client):
            ynab_c = categories_api.CategoriesApi(ynab_client)
            self._map = defaultdict(lambda: None)
            self._names = {''}  # Because we don't mind empty string as a category name
            resp = ynab_c.get_categories(YNAB_BUDGET_ID)
            for cg in resp['data']['category_groups']:
                # pprint(cg)
                for c in cg['categories']:
                    self._map[c['name']] = c['id']
                    self._names.add(c['name'])

        def get_id(self, name):
            return self._map[name]

        def get_names(self):
            return self._names

    def _make_ynab_client(self):
      with open(YNAB_SECRETS_FILE) as f:
          secrets = json.load(f)
          api_key = secrets['api_key']
      config = ynab_api.Configuration(
          host="https://api.youneedabudget.com/v1")
      config.api_key['bearer'] = api_key
      config.api_key_prefix['bearer'] = 'Bearer'
      return ynab_api.ApiClient(config)

    def _make_transaction(self, ynab_account_id, row):
        if not ynab_account_id:
            raise "Must provide tiller_id"
        # pprint(row)
        if not row['Description']:
            pprint(row, file=sys.stderr)
            raise('Empty description')
        result = {
            'account_id': ynab_account_id,
            'amount': round(row['Amount'] * 1000),
            'date': date_from_excel_date(row['Date']),
            'import_id': row['tiller_transaction_id'],
            'payee_name': row['Description'][:50], # required on read but not write ?!
            'memo': row['Full Description'][:200]
        }
        c = row['Category']
        if c:
            result['category_name'] = c
            result['category_id'] = self._categories.get_id(c)
        return result

    def _get_ynab_account_name_id_map(self):
        return { a['name'] : a['id'] 
                 for a in self._ynab_a.get_accounts(YNAB_BUDGET_ID)['data']['accounts'] }

    def get_ynab_transactions(self, account_id):
        return self._ynab_t.get_transactions_by_account(
            YNAB_BUDGET_ID, 
            account_id
        )['data']['transactions']

    def get_all_ynab_transactions(self, **kwargs):
        return self._ynab_t.get_transactions(
            YNAB_BUDGET_ID,
            **kwargs
        )['data']['transactions']

    def _update_ynab_internal(self):
        tiller_values = self._spreadsheets.values().get(
            spreadsheetId=TMP_SPREADSHEET_ID, range=RANGE_NAME,
            valueRenderOption='UNFORMATTED_VALUE').execute().get('values', [])

        if not tiller_values:
            raise('Empty tiller results.')

        tiller_headers = tiller_values[0]
        tiller_entry_list = [
            defaultdict(str, { tiller_headers[i] : row[i] for i in range(len(row)) })
            for row in tiller_values[1:] 
        ]
        tiller_entry_tiller_ids = set(
            [entry['tiller_transaction_id'] for entry in tiller_entry_list])

        # print(tiller_entry_tiller_ids)

        ynab_tiller_values = self._spreadsheets.values().get(
            spreadsheetId=TMP_SPREADSHEET_ID, range='ynab_tiller_import!A:C',
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

        new_tiller_ids = tiller_entry_tiller_ids.difference(ynab_tiller_entry_tiller_ids)
        print('new_tiller_ids', new_tiller_ids)
        long_tiller_ids = [id for id in new_tiller_ids if len(id) > 36]
        if long_tiller_ids:
            raise Exception('long_tiller_ids ' + str(long_tiller_ids))
            

        # pprint(tiller_entry_list[0])
        skipped_categories = set()
        ynab_transactions = []
        for entry in tiller_entry_list:
            if not self._the_account_name:
                self._the_account_name = entry['Account']
            elif entry['Account'] != self._the_account_name:
                raise(' '.join(('Please only use one account name!', 
                                self._the_account_name, entry['Account'])))

            if entry['tiller_transaction_id'] not in new_tiller_ids:
                continue
            if entry['category_name'] not in self._categories.get_names():
                skipped_categories.add(entry['category_name'])
                continue
            ynab_transactions.append(SaveTransaction(
                **self._make_transaction(self._ynab_account_name_id_map[entry['Account']], entry)))
            
        for c in skipped_categories:
            print(c, file=sys.stderr)
        if skipped_categories:
            raise Exception('CATEGORIES MISSING FROM YNAB!!!')

        if not ynab_transactions:
            return
        
        api_response = self._ynab_t.create_transaction(
            YNAB_BUDGET_ID,
            PostTransactionsWrapper(transactions=ynab_transactions)
        )
        # pprint(api_response)
        return api_response['data']

    def _apply_tiller_ynab_sheet_updates(self, new_sheets_row_maps):
        # print('THROMER _apply_tiller_ynab_sheet_updates')
        # pprint(new_sheets_row_maps)
        result = self._spreadsheets.values().get(
            spreadsheetId=TMP_SPREADSHEET_ID, range='ynab_tiller_import!1:1',
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
            spreadsheetId=TMP_SPREADSHEET_ID, 
            range='ynab_tiller_import!A:C',
            body={
                'range': 'ynab_tiller_import!A:C',
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

    def _recover_from_duplicate_import_ids(self, account_id, import_ids):
        # print('THROMER _recover_from_duplicate_import_ids')
        import_ids = set(import_ids)
        transactions = self.get_ynab_transactions(account_id)
        self._apply_tiller_ynab_sheet_updates([ 
            self._tiller_ynab_sheet_row_map(transaction)
            for transaction in transactions
            if (transaction['import_id'] in import_ids and
                not transaction['deleted']) ])

    def update_ynab(self):
        # print('THROMER update_ynab')
        ynab_data = self._update_ynab_internal()
    
        if ynab_data and ynab_data['duplicate_import_ids']:
            # print('THROMER uh oh duplicates 1')
            # This could happen if we update YNAB but fail to note it in Sheets.
            self._recover_from_duplicate_import_ids(
                self._ynab_account_name_id_map[self._the_account_name],
                ynab_data['duplicate_import_ids'])
            ynab_data = self._update_ynab_internal()
            if ynab_data and ynab_data['duplicate_import_ids']:
                # print('THROMER uh oh duplicates 2')
                for id in ynab_data['duplicate_import_ids']:
                    print(id, file=sys.stderr)
                raise Exception('Uh oh, unexpected duplicate import_ids even after repair ' + str(ynab_data['duplicate_import_ids']))

        if ynab_data:
            self._update_tiller_ynab_sheet(ynab_data['transactions'])


def none_blank(s):
    return "" if s == None else s

def main():
    print("probably don't want to run this any more!!!")
    sys.exit(1)
    m = Main()

    if False:
        all = m.get_ynab_transactions(
            YNAB_AMAZON_SPLIT_ACCOUNT_ID,
            # Or not:
            # since_date=(datetime.date.today() - 
            #            datetime.timedelta(5)).strftime('%Y-%m-%d')
        )
        # print(pformat(all), file=sys.stderr)
        # print(len(all), file=sys.stderr)

        result = [
            {
                'tiller_transaction_id': none_blank(t['import_id']),
                'ynab_transaction_id': str(t['id']),
	        'date': str(date_to_excel_date(t['date'])),
                'Amount': f"{(round(t['amount']/1000.0, 2)):.2f}",
                'Account': none_blank(t['account_name']),
                'Category': none_blank(t['category_name']),
                'Description': none_blank(t['payee_name'])
            } for t in all]

        dw = csv.DictWriter(sys.stdout, [
            'tiller_transaction_id', 
            'ynab_transaction_id',
	    'date',
	    'Amount',
            'Account',
            'Category',
            'Description'
        ], lineterminator='\r\n', extrasaction='ignore')

        dw.writeheader()
        for row in sorted(result, key=operator.itemgetter('tiller_transaction_id')):
            dw.writerow(row)
        return

    if False:
        m.update_ynab()
    
    if False:
        pprint(m.get_all_ynab_transactions())

if __name__ == '__main__':
    main()

# Local Variables:
# compile-command: "python ynab-import.py"
# End:    
