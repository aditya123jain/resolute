# import logging
from kiteconnect import KiteTicker,KiteConnect
import pandas as pd
import sqlite3
import io
import requests
# import logging
import numpy as np
from kiteconnect import KiteTicker,KiteConnect
import os

# logging.basicConfig(level=logging.DEBUG)
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

import json

try:
    # Open the JSON file in read mode ('r')
    with open(os.path.join(DATA_DIR, 'credentials.json')) as file:
        # Load the JSON data from the file
        data = json.load(file)

    # Now 'data' contains the content of the JSON file as a Python object
    print(f"data\n {data}")

    # You can access specific elements like a dictionary
    if isinstance(data, dict) and 'name' in data:
        print(f"Name: {data['name']}")

except FileNotFoundError:
    print("Error: The file 'data.json' was not found.")
except json.JSONDecodeError:
    print("Error: Could not decode JSON from the file. Check if it's valid JSON.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")

# with open('credentials.json', 'r') as file:
#     # Load the JSON data from the file
#     data = json.load(file)
#
#     # Now 'data' contains the content of the JSON file as a Python object
# print(f"data\n {data}")

api_key = data['apikey']
api_secret = data['api_secret']
userid = data['userid']
password = data['password']
totp_secret = data['totp_secret']


# Initialise
kws = KiteTicker(api_key, api_secret)

'''Creating the table -- STEP 1'''
kite = KiteConnect(api_key=api_key)
df = pd.DataFrame(kite.instruments())
print(df.head())

# _symbol_df = df[df['segment'] == 'NFO-FUT']

# # df_nse = # _symbol_df = df[df['segment'] == 'NFO-FUT']
# req = requests.get(f'')
# print(req)

# resp = requests.get(
#     "https://nsearchives.nseindia.com/content/indices/ind_nifty200list.csv", headers={
#         "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15"
#     }
# )
# print(resp.text)

# df_nse = pd.read_csv(io.StringIO(resp.text))

# #pd.read_csv('ind_nifty200list.csv')
# print(df_nse.tail())

df_nse = pd.read_csv(os.path.join(DATA_DIR, 'MW-SECURITIES-IN-F&O.csv'))

result = df[
    (
        (df['name'].isin(df_nse['SYMBOL \n']) & (df['segment'] == 'NFO-FUT'))
        |
        (df['tradingsymbol'].isin(df_nse['SYMBOL \n']) & (df['instrument_type'] == 'EQ') & (df['exchange'] == 'NSE'))
    )
]

result_new = result[['tradingsymbol', 'instrument_token', 'name', 'expiry']].copy()
result_new['LTP'] = 0
result_new['TOP_BID'] = 0
result_new['TOP_ASK'] = 0
print(result_new.head())
result_new.to_csv(os.path.join(DATA_DIR, 'all_inst.csv'))
conn = sqlite3.connect(os.path.join(DATA_DIR, 'trading_data.db'))
result_new.to_sql('new_ins', conn, if_exists='replace', index=False)
print(result_new.head(5))

result_new['expiry'] = pd.to_datetime(result_new['expiry'])
# Assuming your DataFrame is named df
unique_months = result_new['expiry'].dt.strftime('%b').str.upper().unique()
print(unique_months)
Current_month = unique_months[0]
NEAR_FAR_month = unique_months[1]
FARTHEST_month = unique_months[2]

#############################################################################################

# Initialise
# kws = KiteTicker("mwyzdvhb0ud0a72k", "ioma29xndbypol3ejtdrpe7sxku8y7g9")

'''Creating the table'''
conn = sqlite3.connect(os.path.join(DATA_DIR, "trading_data.db"))
cursor = conn.cursor()

# Get a list of all table names
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

# Create a dictionary of DataFrames, one per table
dfs = {}
for table_name in tables:

    # Current_month = 'JUN'
    # NEAR_FAR_month = 'JUL'
    # FARTHEST_month = 'AUG'


    table = table_name[0]  # fetch the string from tuple
    dfs[table] = pd.read_sql_query(f"SELECT * FROM {table}", conn)
    print(dfs[table])
    token_list = dfs[table]['instrument_token'].to_list()
    print(token_list)
    print(f"✅ Loaded '{table}' with {len(dfs[table])} rows")
    df = dfs[table]
    df['name'] = np.where(df['expiry'] == '', df['tradingsymbol'], df['name'])
    # # Step 1: Create a column to identify the month from tradingsymbol
    df['month'] = df['tradingsymbol'].str.extract(Fr'({Current_month}|{NEAR_FAR_month}|{FARTHEST_month})')
    df.to_csv(os.path.join(DATA_DIR, 'check_.csv'))
    print(f"✅ df '{table}' with\n {df.head()} \n ")

    # # Step 2: Pivot the DataFrame for each attribute (tradingsymbol, instrument_token, LTP)
    pivot_tradingsymbol = df.pivot(index='name', columns='month', values='tradingsymbol')
    pivot_instrument = df.pivot(index='name', columns='month', values='instrument_token')
    pivot_ltp = df.pivot(index='name', columns='month', values='LTP')

    # # Step 3: Rename columns to match desired format
    pivot_tradingsymbol.columns = [f'tradingsymbol_{col}' for col in pivot_tradingsymbol.columns]
    pivot_instrument.columns = [f'instrument_token_{col}' for col in pivot_instrument.columns]
    pivot_ltp.columns = [f'LTP_{col}' for col in pivot_ltp.columns]

    # # Step 4: Merge the pivoted DataFrames
    result = pd.concat([pivot_tradingsymbol, pivot_instrument, pivot_ltp], axis=1).reset_index()

    months = ['nan', Current_month, NEAR_FAR_month, FARTHEST_month]
    for month in months:
        ltp_col = f'LTP_{month}'
        bid_col = f'TOP BID_{month}'
        ask_col = f'TOP ASK_{month}'

        # Insert TOP BID and TOP ASK columns after LTP
        result[bid_col] = result[ltp_col] * 0.99
        result[ask_col] = result[ltp_col] * 1.01

        # Reorder columns to place TOP BID and TOP ASK right after LTP
        cols = result.columns.tolist()
        ltp_idx = cols.index(ltp_col)
        cols.insert(ltp_idx + 1, cols.pop(cols.index(bid_col)))
        cols.insert(ltp_idx + 2, cols.pop(cols.index(ask_col)))
        result = result[cols]

    # Step 5: Reorder columns to match the desired output
    desired_columns = [
        'name',
        'tradingsymbol_nan', 'instrument_token_nan', 'LTP_nan','TOP BID_nan','TOP ASK_nan',

        f'tradingsymbol_{Current_month}', f'instrument_token_{Current_month}', f'LTP_{Current_month}',f'TOP BID_{Current_month}', f'TOP ASK_{Current_month}',
        f'tradingsymbol_{NEAR_FAR_month}', f'instrument_token_{NEAR_FAR_month}', f'LTP_{NEAR_FAR_month}',f'TOP BID_{NEAR_FAR_month}', f'TOP ASK_{NEAR_FAR_month}',
        f'tradingsymbol_{FARTHEST_month}', f'instrument_token_{FARTHEST_month}', f'LTP_{FARTHEST_month}', f'TOP BID_{FARTHEST_month}', f'TOP ASK_{FARTHEST_month}'

    ]
    result = result[desired_columns]

    result.to_csv(os.path.join(DATA_DIR, 'CSV_with_Instrument_tokens.csv'))

    #
    # # Display the result
    print(result.head())



#############################################################################################
# import logging
import numpy as np
from kiteconnect import KiteTicker,KiteConnect
import pandas as pd
import sqlite3
# import gspread
# from gspread_dataframe import set_with_dataframe

# logging.basicConfig(level=logging.DEBUG)
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)


df = pd.read_csv(os.path.join(DATA_DIR, 'CSV_with_Instrument_tokens.csv'))
print(df.head())

# set_with_dataframe(worksheet, df.dropna(), include_index=False, include_column_header=True)

df.dropna().to_csv(os.path.join(DATA_DIR, 'ALL_DATA_original.csv'))

df.dropna().to_csv(os.path.join(DATA_DIR, 'ALL_DATA_back_to_old.csv'))

############################################################################################
import pandas as pd
# import gspread
# from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials
from kiteconnect import KiteTicker, KiteConnect
import logging
from threading import Thread, Lock
import time
import numpy as np
import pyotp
import requests
import pandas as pd

##############################################   check for similar column #######################
df_old1 = pd.read_csv(os.path.join(DATA_DIR, 'ALL_DATA_back_to_old.csv'))
df_old2 = pd.read_csv(os.path.join(DATA_DIR, 'ALL_DATA_original.csv'))

if df_old2[f'instrument_token_{Current_month}'].iloc[0] == df_old2[F'instrument_token_{NEAR_FAR_month}'].iloc[0]:
    print(f'Both instrument become same. changing back')
    df_old1.to_csv(os.path.join(DATA_DIR, 'ALL_DATA_original.csv'))

# print(df_old2['instrument_token_JUN'].iloc[0] == df_old2['instrument_token_JUL'].iloc[0])
# print(df_old2['instrument_token_JUL'].iloc[0])
#################################################################################################

# Read the CSV file

# Keep only the header row and save
# df.iloc[:0].to_csv('your_file.csv', index=False)

# api_key = "mwyzdvhb0ud0a72k"
# api_secret = "ioma29xndbypol3ejtdrpe7sxku8y7g9"
# userid = "YP2866"
# password = "123abc@@"
# totp_secret = "WXJ3TVZZB7EHJ5QG5SFA4OQOFCZJBGYZ"

"""Handles login to Zerodha and sets access token."""
loginurl = "https://kite.zerodha.com/api/login"
twofaUrl = "https://kite.zerodha.com/api/twofa"
twofa = f"{pyotp.TOTP(totp_secret).now()}"
reqSession = requests.Session()
request_id = \
    reqSession.post(loginurl, data={"user_id": userid, "password": password}).json()["data"][
        "request_id"]
reqSession.post(twofaUrl,
                data={"user_id": userid, "request_id": request_id, "twofa_value": twofa}).json()
API_Session = reqSession.get(f"https://kite.trade/connect/login?v=3&api_key={api_key}")
request_token = API_Session.url.split("request_token=")[1].split("&")[0]

kite = KiteConnect(api_key=api_key)
data = kite.generate_session(request_token, api_secret=api_secret)
access_token = data['access_token']
kite.set_access_token(access_token)

print(f'ZERODHA ACCESS TOKEN IS {access_token}')
logging.info(f'ZERODHA ACCESS TOKEN IS {access_token}')

pd.set_option('display.max_columns', None)

pd.set_option('display.max_rows', None)

liveFeedDict = {}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


##############################

try:

    df = pd.read_csv(os.path.join(DATA_DIR, 'ALL_DATA_original.csv'))

    # df.to_csv('ALL_DATA.csv', index=False, header=False)

    print(f'df_ap\n', df.head())


except Exception as e:
    logging.error(f"Error loading data: {e}")
    exit(1)

token_to_month_col = {}
all_tokens = set()



# sys.exit()
for month, token_col in [('nan', 'instrument_token_nan'), (f'{Current_month}', f'instrument_token_{Current_month}'),
                         (FARTHEST_month, f'instrument_token_{FARTHEST_month}'),
                         (NEAR_FAR_month, f'instrument_token_{NEAR_FAR_month}')]:

    print(token_col)

    # tokens = df[token_col].astype(int).tolist()
    tokens = df[token_col].astype(float).astype(int).tolist()
    all_tokens.update(tokens)
    for token in tokens:
        token_to_month_col[token] = {
            'month': month,
            'ltp_col': f'LTP_{month}',
            'bid_col': f'TOP BID_{month}',
            'ask_col': f'TOP ASK_{month}'
        }
token_list = list(all_tokens)
print(f'Subscribing to {len(token_list)} tokens: {token_list}')
logging.info(f"Subscribing to {len(token_list)} tokens: {token_list}")



def update_sheet_df(live_df, sheet_df, _worksheet):
    """
    Update sheet_df with values from live_df for LTP, TOP BID, and TOP ASK columns
    and write the updated DataFrame to Google Sheets.

    """
    print(f'update started')



def monitor_tables():
    table_stats = {'instruments': {'row_count': len(df),
                                   'ltp_sum': df[['LTP_APR', 'LTP_MAY', 'LTP_JUN']].astype(float).sum().sum()}}
    while True:
        time.sleep(1)
        current_row_count = len(df)
        current_ltp_sum = df[['LTP_APR', 'LTP_MAY', 'LTP_JUN']].astype(float).sum().sum()
        if (current_row_count != table_stats['instruments']['row_count'] or
                current_ltp_sum != table_stats['instruments']['ltp_sum']):
            logging.info(f"DataFrame changed! Current data (top 5 rows):")
            logging.info(df.head(5).to_string())
            table_stats['instruments']['row_count'] = current_row_count
            table_stats['instruments']['ltp_sum'] = current_ltp_sum
        time.sleep(1)




df_lock = Lock()

from concurrent.futures import ThreadPoolExecutor

df_old = pd.read_csv(os.path.join(DATA_DIR, 'ALL_DATA_original.csv'))


def _insert_df(_in_df):
    start_time = time.time()
    try:
        df = pd.read_csv(os.path.join(DATA_DIR, 'ALL_DATA_original.csv'))
    except Exception as e:
        print(f' error in reading orignal book {e}')
        return None
    # file_path = 'D:\data\OneDrive - Samruddhi Investors Services Private Limited'

    # df = pd.read_excel('Book1.xlsx',
    #                    sheet_name='Sheet1')
    #
    # print(df.head())

    # df = pd.read_excel('Book1.xlsx',
    #                    sheet_name='Sheet1')
    #
    # print(df.head())

    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

    # if df.empty:
    #     df = gs_df
    #
    # print(f'Df before csv \n {df.head()}')

    _in_df['ltp'] = _in_df['last_price']
    _in_df['bestBuyPrice'] = _in_df['depth'].str['buy'].str[0].str['price'].fillna(0)
    _in_df['bestSellPrice'] = _in_df['depth'].str['sell'].str[0].str['price'].fillna(0)

    tick_df = _in_df.loc[:, ['instrument_token', 'ltp', 'bestBuyPrice', 'bestSellPrice']].copy()
    tick_df['instrument_token'] = tick_df['instrument_token'].astype(int)

    # Pre-process df outside the loop
    with df_lock:
        # df = df.copy()  # Avoid modifying locked df directly
        months = ['nan', Current_month, NEAR_FAR_month, FARTHEST_month]

        # Pre-compute all merges in one go
        def process_month(month):
            token_col = f'instrument_token_{month}'
            ltp_col = f'LTP_{month}'
            bid_col = f'TOP BID_{month}'
            ask_col = f'TOP ASK_{month}'

            # Convert to numeric once
            df[token_col] = pd.to_numeric(df[token_col], errors='coerce').fillna(0).astype(int)

            # Vectorized merge and update - much faster than iterrows()
            merge_df = df[df[token_col].notna()][['name', token_col]].merge(
                tick_df,
                left_on=token_col,
                right_on='instrument_token',
                how='inner'
            )

            if not merge_df.empty:
                # Create mapping dictionary for fast lookup
                update_map = merge_df.set_index(token_col)[['ltp', 'bestBuyPrice', 'bestSellPrice']].to_dict('index')

                # Vectorized update using map - 100x faster than iterrows
                tokens_to_update = merge_df[token_col].unique()
                mask = df[token_col].isin(tokens_to_update)

                df.loc[mask, ltp_col] = df.loc[mask, token_col].map(lambda x: update_map[x]['ltp'])
                df.loc[mask, bid_col] = df.loc[mask, token_col].map(lambda x: update_map[x]['bestBuyPrice'])
                df.loc[mask, ask_col] = df.loc[mask, token_col].map(lambda x: update_map[x]['bestSellPrice'])

                logging.info(f"{month} with {len(merge_df)} tokens: {merge_df['instrument_token'].tolist()}")

            return month

        # Parallel processing for months
        with ThreadPoolExecutor() as executor:
            list(executor.map(process_month, months))

        # Batch update worksheet - single write instead of multiple
        # set_with_dataframe(worksheet, df, include_index=False, include_column_header=True)
        # df['"'] = 0

        '''
        print('sorted df\n', df.iloc[1:].sort_values(by='name'))

        __sorted_df = df.sort_values(by='name').iloc[1:]

        # __sorted_df.drop(columns=__sorted_df.columns, inplace=True)

        print(f' __sorted_df \n {__sorted_df.head()}' )
        __sorted_df.to_csv(os.path.join(DATA_DIR, 'ALL_DATA.csv'), index=False)



        '''
        df.to_csv(os.path.join(DATA_DIR, 'ALL_DATA.csv'), index=False)

        print(f' __sorted_df \n {df.head()}')

        # print(df.iloc[:0].to_csv('ALL_DATA.csv',index=False))

        # df.to_csv('ALL_DATA.csv', mode='a', index=False, header=False)

        print(df.head())

        print(f'length of new df \n {len(df)}')

        if len(df) == len(df_old):
            print('length matched')
            df.to_csv(os.path.join(DATA_DIR, 'ALL_DATA_original.csv'))

        # df.to_csv(file_path)

        # df.to_excel('Book1.xlsx')
        # df = pd.read_excel('Book1.xlsx',
        #                    sheet_name='ALL_DATA')
        #
        # print(df.head())

    logging.info(f"Processing completed in {time.time() - start_time:.2f} seconds")

    ############################################################################




def processTicks(*tickData):
    # print(f'length of the tickData:\n  {pd.DataFrame(tickData).head()}')

    tick_df = pd.DataFrame(tickData)

    # time.sleep(10)

    Thread(target=_insert_df, args=(tick_df,)).start()

    #

# WebSocket callbacks
def on_ticks(ws, ticks):
    # print(f'ticks {ticks}')

    Thread(target=processTicks, args=(ticks)).start()


def on_connect(ws, response):
    logging.info(f"WebSocket connected: {response}")
    ws.subscribe(token_list)
    ws.set_mode(ws.MODE_FULL, token_list)
    logging.info(f"Subscribed to {len(token_list)} tokens in MODE_FULL")


def on_close(ws, code, reason):
    logging.info(f"WebSocket closed: code={code}, reason={reason}")
    ws.stop()


# Initialize KiteTicker
kws = KiteTicker(api_key, access_token)
kws.on_ticks = on_ticks
kws.on_connect = on_connect
kws.on_close = on_close

# Start monitoring thread
# monitor_thread = Thread(target=monitor_tables, daemon=True)


# monitor_thread.start()


if __name__ == '__main__':
    try:
        # Thread(target=push_dataframe).start()
        kws.connect()
        # get_live_feed()

    except Exception as e:
        logging.error(f"Error connecting to WebSocket: {e}")

##########################################################################################