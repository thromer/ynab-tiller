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

Re-creating cloud schedule if needed

gcloud scheduler jobs create pubsub daily --location=us-west1 --schedule='17 5 * * *' --topic=projects/ynab-sheets-001/topics/topic-001 --message-body=' ' --time-zone='America/Los_Angeles'

Deployment

cd src/ynab-tiller && gcloud --project ynab-sheets-001 functions deploy ynab-tiller --region=us-west1 --trigger-topic=topic-001 --runtime=python39
