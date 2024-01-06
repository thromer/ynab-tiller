New machine

* git clone 
* venv venv
* . venv/bin/activate
* pip install -r requirements.txt
* gcloud auth login tromer@gmail.com --enable-gdrive-access --update-adc --billing-project seventh-torch-825
* gcloud config set project ynab-sheets-001

Assumptions

- We'll assume we never have two instances running concurrently.
- The only sheet this script will ever modify is 'ynab-tiller'.
- The 'Brokerage' sheet contains all transactions for the last 40 days.
- We'll run this no less than every 30 days.

Cookie crumbs

sudo apt-get install python3-venv
venv venv
. venv/bin/activate

Later: https://github.com/dmlerner/ynab-python  (ynab-api ?)

https://developers.google.com/sheets/api/quickstart/python

Not: https://github.com/swagger-api/swagger-codegen#prerequisites

Not: https://openapi-generator.tech/docs/installation#jarhttps://converter.swagger.io/#/Converter/convertByUrl

Cloud project

https://console.cloud.google.com/welcome?pli=1&project=ynab-sheets-001

pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
pip install git+https://github.com/thromer/ynab-api.git@thromer-nullable

pip install datetime

