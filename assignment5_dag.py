# -*- coding: utf-8 -*-
"""assignment5 dag

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1ma8G2BhDRaBzeLP_pCqb-SqxCYifUUqA
"""

#pip install airflow
from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.decorators import task
from airflow.models import Variable
from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook
#pip install requests
#pip install snowflake-connector-python
import requests
import snowflake.connector
import pandas as pd
import json


#The snowflake setup is like this:
#CREATE DATABASE hw5_DB;
#CREATE SCHEMA RAW_DATA_SCHEMA;

#CREATE WAREHOUSE hw5_WH
#    WITH
#    WAREHOUSE_SIZE = 'XSMALL'


#The Airflow has variables:
#snowflake_account
#snowflake_password
#snowflake_username
#symbol1
#vantage_api_key

#the Airflow has a snowflake-connection

#the composer environment has pypi packages
#apache-airflow-providers-snowflake
#snowflake-connector-python



def return_snowflake_conn():

    user_id = Variable.get('snowflake_username')
    password = Variable.get('snowflake_password')
    account = Variable.get('snowflake_account')

    conn = snowflake.connector.connect(
        user = user_id,
        password = password,
        account = account,
        warehouse = "hw5_WH",
        DATABASE = "hw5_DB",
        SCHEMA = "RAW_DATA_SCHEMA",
        role = "ACCOUNTADMIN"
      )
    return conn.cursor()


@task
def extract(url):
  r = requests.get(url)
  data = r.json()

  return data


@task
def transform(data):
  results = []
  for d in data["Time Series (Daily)"]:
    stock_info = data["Time Series (Daily)"][d]
    stock_info["date"] = d
    results.append(stock_info)


  return results


@task
def load(cursor, results, table, symbol):
  try:
    cursor.execute("BEGIN;")
    sql_query = f'CREATE OR REPLACE TABLE {table}(date TIMESTAMP_NTZ, open NUMBER, high NUMBER, low NUMBER, close NUMBER, volume NUMBER, symbol VARCHAR, PRIMARY KEY(date));'
    cursor.execute(sql_query)

    for r in results:
      date = r["date"]
      open = r["1. open"]
      high = r["2. high"]
      low = r["3. low"]
      close = r["4. close"]
      volume = r["5. volume"]
      insert_sql = f"INSERT INTO {table}(date, open, high, low, close, volume, symbol) VALUES(TO_TIMESTAMP_NTZ('{date}','yyyy-mm-dd'), {open}, {high}, {low}, {close}, {volume}, '{symbol}');"
      cursor.execute(insert_sql)
    cursor.execute("COMMIT;")
  except Exception as e:
    cursor.execute("ROLLBACK;")
    print(e)
    raise e




with DAG(
    dag_id = 'hw5_etl',
    start_date = datetime(2024,9,21),
    catchup=False,
    tags=['ETL'],
    schedule = '0 2 * * *'
) as dag:
    target_table = "hw5_DB.RAW_DATA_SCHEMA.RAW_DATA"
    api_key = Variable.get("vantage_api_key")
    symbol = Variable.get("symbol1")
    url =f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&interval=5min&apikey={api_key}"
    cursor = return_snowflake_conn()

    data = extract(url)
    results = transform(data)
    load(cursor, results, target_table, symbol)