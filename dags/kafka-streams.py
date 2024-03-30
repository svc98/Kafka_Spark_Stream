import uuid
import json
import time
import requests
import logging
from kafka import KafkaProducer
from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator


default_args = {
    "owner": "svc",
    "start_date": datetime(2024, 3, 26, 11, 00)
}

def get_data():
    res = requests.get('https://randomuser.me/api/')
    res = res.json()
    results = res['results'][0]
    # print(json.dumps(results,indent=3))
    return results

def format_data(results):
    data = {}

    data['id'] = str(uuid.uuid4())
    data['first_name'] = results['name']['first']
    data['last_name'] = results['name']['last']
    data['gender'] = results['gender']

    location = results['location']                                                                                       # JSON outputs values separated, putting them together
    data['address'] = f"{str(location['street']['number'])} {location['street']['name']}, " \
                      f"{location['city']}, {location['state']}, {location['country']}"
    data['post_code'] = location['postcode']
    data['email'] = results['email']
    data['username'] = results['login']['username']
    data['dob'] = results['dob']['date']
    data['registered_date'] = results['registered']['date']

    phone = results['phone']
    data['phone'] = phone.replace("(", "").replace(")", "").replace("-", "").replace(" ", "")
    data['picture'] = results['picture']['medium']

    return data


def stream_data():
    producer = KafkaProducer(bootstrap_servers=['kafka:9092'], api_version=(2,8,4), max_block_ms=120000)
    curr_time = time.time()

    while True:
        if time.time() > curr_time + 120:                                                                                 # Stream for 1 minute
            break
        try:
            raw_data = get_data()
            cleaned_data = format_data(raw_data)
            producer.send('user_created', json.dumps(cleaned_data).encode('utf-8'))
            print('Data Sent!')
        except Exception as e:
            logging.error(f'An error occurred: {e}')
            continue

with DAG(
    dag_id = 'user_ingestion',
    default_args = default_args,
    start_date = datetime(2024, 3, 22, 5, 30),
    schedule_interval = '@daily',
    catchup = False
) as dag:
    streaming_task = PythonOperator(
        task_id = "stream_data_from_api",
        python_callable = stream_data
    )