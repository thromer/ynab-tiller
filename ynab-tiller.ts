import * as fs from 'fs';
import * as env from 'env-var';
import * as ynab from 'ynab';

// If modifying these scopes, delete the file $HOME/ynab-tiller-token.json.
const SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

const SPREADSHEET_ID = '1UQQgW3kBfxNBB50q1pg4Hn2c6DvwoKVUF_9GelZ1k1Q'
const RANGE_NAME = 'Brokerage!A:G'

const HOME_DIR = env.get('HOME').asString()
const TOKEN_FILE = HOME_DIR + '/ynab-tiller-token.json'
const CREDENTIALS_FILE = HOME_DIR + '/client_secret_503586827022-4det1688u753c66bgkplrn1eseno78bq.apps.googleusercontent.com.json'
const YNAB_BUDGET_ID = 'de4c0d69-c96c-4f1d-833b-cb0b7151b364';
const YNAB_BROKERAGE_ACCOUNT_ID = '93132634-e507-4c48-909d-981aef2cc70e';
const YNAB_CAPITAL_ONE_ACCOUNT_ID = '4c00380e-ee8e-4fc6-9df0-e0e845ec8bbd';
const YNAB_API_KEY = fs.readFileSync(HOME_DIR + '/ynab-api-key', 'utf-8');

const ynabAPI = new ynab.API(YNAB_API_KEY);
const transactionsApi = ynabAPI.transactions;

(async function() {
  const transactionsResponse = await transactionsApi.getTransactionsByAccount(
    YNAB_BUDGET_ID, YNAB_CAPITAL_ONE_ACCOUNT_ID, '2023-06-07'); //  YNAB_BROKERAGE_ACCOUNT_ID);
    // '2023-01-01', undefined, undefined);
  const transactions = transactionsResponse.data.transactions;
  for (let transaction of transactions) {
    let k: keyof typeof transaction;
    for (k in transaction) {
      console.log(`${k} ${transaction[k]}`);
    }
    // for (const [k, v] of Object.entries
  }
})();
