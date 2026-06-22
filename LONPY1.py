# ==============================
# CONFIGURATION
# ==============================
#import MetaTrader5 as mt5
SYMBOL = "EURUSD"

#TIMEFRAME = mt5.TIMEFRAME_M1

LOT_SIZE = 0.10

BB_PERIOD = 20
BB_STD_DEV = 2

BREAKOUT_THRESHOLD = 0.0005   # 0.05%

USE_VOLUME_FILTER = True

USE_STOPLOSS = True

HOLDING_HOURS = 4

MAGIC_NUMBER = 999001

IST_START_HOUR = 12
IST_START_MINUTE = 0

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, timedelta
import time
from time import time, sleep
from datetime import datetime, UTC
# ====================================
# CONFIG
# ====================================

SYMBOL = "XAUUSD"
TIMEFRAME = mt5.TIMEFRAME_M1

LOT_SIZE = 0.10

BB_PERIOD = 20
BB_STD_DEV = 2

BREAKOUT_THRESHOLD = 0.0005      # 0.05%

USE_VOLUME_FILTER = True
USE_STOPLOSS = True

HOLDING_HOURS = 4

MAGIC_NUMBER = 999001

IST = pytz.timezone("Asia/Kolkata")

# ====================================
# MT5 CONNECT test Mt5 connection and print account balance

# ====================================

def connect_to_mt5():
    path_to_terminal = r"C:\\Program Files\\MetaTrader 5\\terminal64.exe"
    account_number = 5052003214    #41108363  # Must be an integer, not a string
    account_password = "Cm@5XaSw" # "Swami$123"  # _pW2VeXz
    broker_server = "MetaQuotes-Demo" 


    max_retries = 3
    for attempt in range(max_retries):
        if mt5.initialize(path=path_to_terminal, login=account_number, password=account_password, server=broker_server):
            print("Connected to MetaTrader5")
            break
        else:
            error = mt5.last_error()
            print(f"Attempt {attempt + 1} failed: {error}")
            if attempt < max_retries - 1:
                sleep(2)  # Wait 2 seconds before retry
            else:
                print("Failed to initialize after retries")
                mt5.shutdown()
                return
            


    if not mt5.symbol_select(SYMBOL, True):
        print("symbol_select() failed, symbol=", SYMBOL, "error code =", mt5.last_error())
        mt5.shutdown()
        return
    
    price_info = mt5.symbol_info_tick(SYMBOL)
    if price_info is None:
        print("symbol_info_tick() tick failed, symbol=", SYMBOL, "error code =", mt5.last_error())
        mt5.shutdown()
        return

    


def print_account_balance():
    account_info = mt5.account_info()
    if account_info is None:
        print("Failed to get account info:", mt5.last_error())
        return

    print(f"Account balance: {account_info.balance:.2f} {account_info.currency}")
    print(f"Equity: {account_info.equity:.2f} {account_info.currency}")
    print(f"Free margin: {account_info.margin_free:.2f} {account_info.currency}")
    return account_info


# ====================================
# GLOBAL STATE
# ====================================

pending_signal = None

active_buy = False
active_sell = False

trade_tracker = {}


# ====================================
# GET DATA
# ====================================

def get_rates(symbol, bars=200):

    rates = mt5.copy_rates_from_pos(
        symbol,
        TIMEFRAME,
        0,
        bars
    )

    df = pd.DataFrame(rates)

    df['time'] = pd.to_datetime(df['time'], unit='s')

    return df


# ====================================
# BOLLINGER BANDS
# ====================================

def calculate_bollinger(df):

    df["sma"] = (
        df["close"]
        .rolling(BB_PERIOD)
        .mean()
    )

    std = (
        df["close"]
        .rolling(BB_PERIOD)
        .std()
    )

    df["upper"] = df["sma"] + BB_STD_DEV * std
    df["lower"] = df["sma"] - BB_STD_DEV * std

    return df


# ====================================
# SESSION FILTER
# ====================================

def strategy_active():

    now = datetime.now(IST)
    
    if now.hour >= IST_START_HOUR:
        #print("Strategy Active for:", IST_START_HOUR, ". Current time:", now.hour, ":", now.minute)
        return True
    else:
        print("Strategy not active yet for:", IST_START_HOUR, ". Current time:", now.hour, ":", now.minute)
        return False
    
    if now.hour == IST_START_HOUR and now.minute >= 0:
        return True
    else:
        print("Strategy not active yet for:", IST_START_HOUR, ". Current time:", now.hour, ":", now.minute)
        return False
    
    return False


# ====================================
# POSITION CHECK
# ====================================

def get_open_positions():

    positions = mt5.positions_get(symbol=SYMBOL)

    if positions is None:
        return []

    return positions


# ====================================
# PLACE ORDER
# ====================================

def place_order(direction, sl_price=None):

    tick = mt5.symbol_info_tick(SYMBOL)

    if direction == "BUY":
        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask
    else:
        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid

    request = {

        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": LOT_SIZE,
        "type": order_type,
        "price": price,
        "magic": MAGIC_NUMBER,
        "comment": "London_BB",

        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC
    }

    if sl_price is not None:
        request["sl"] = sl_price

    result = mt5.order_send(request)

    print(result)

    if result.retcode == mt5.TRADE_RETCODE_DONE:

        trade_tracker[result.order] = {
            "entry_time": datetime.utcnow(),
            "direction": direction
        }

        print(
            f"{direction} OPENED"
        )

    return result


# ====================================
# CLOSE POSITION
# ====================================

def close_position(position):

    tick = mt5.symbol_info_tick(position.symbol)

    if position.type == mt5.POSITION_TYPE_BUY:

        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid

    else:

        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask

    request = {

        "action": mt5.TRADE_ACTION_DEAL,
        "position": position.ticket,
        "symbol": position.symbol,
        "volume": position.volume,
        "type": order_type,
        "price": price,
        "magic": MAGIC_NUMBER,
        "comment": "TimeExit",

        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC
    }

    result = mt5.order_send(request)

    print(
        f"Position Closed : {position.ticket}"
    )

    return result


# ====================================
# EXIT AFTER 4 HOURS
# ====================================

def manage_exits():

    positions = get_open_positions()


    #now = datetime.utcnow()
    now = datetime.now(UTC)
    for pos in positions:

        entry_time = datetime.now(
            pos.time
        )

        if now >= entry_time + timedelta(hours=HOLDING_HOURS):

            close_position(pos)


# ====================================
# SIGNAL GENERATION
# ====================================

def check_signal():
    
    global pending_signal
    #print("check_signal pending_signal:", pending_signal)
    if not strategy_active():
        return

    df = get_rates(SYMBOL)
    #print(df)
    df = calculate_bollinger(df)

    candle = df.iloc[-2]

    close = candle["close"]

    upper = candle["upper"]
    lower = candle["lower"]
    
    volume = candle["tick_volume"]

    avg_volume = (
        df["tick_volume"]
        .rolling(20)
        .mean()
        .iloc[-2]
    )
    #print("DEBUG: close=", close, "upper=", upper * (1 + BREAKOUT_THRESHOLD),
    #       "lower=", lower * (1 - BREAKOUT_THRESHOLD), "BREAKOUT_THRESHOLD=", BREAKOUT_THRESHOLD,"VOLUME=", volume, "avg_volume=", avg_volume)
    # ---------------------
    # BUY BREAKOUT
    # ---------------------

    if close > upper * (1 + BREAKOUT_THRESHOLD):

        #if USE_VOLUME_FILTER:

        #    if volume <= avg_volume:
        #        return

        pending_signal = {

            "direction": "BUY",
            "sl": candle["low"]
        }

        print("BUY SIGNAL",candle["low"])

    # ---------------------
    # SELL BREAKOUT
    # ---------------------

    elif close < lower * (1 - BREAKOUT_THRESHOLD):

        #if USE_VOLUME_FILTER:

        #    if volume <= avg_volume:
        #        return

        pending_signal = {

            "direction": "SELL",
            "sl": candle["high"]
        }

        print("SELL SIGNAL",candle["high"])


# ====================================
# EXECUTE NEXT BAR OPEN
# ====================================

def execute_pending_signal():

    global pending_signal
    #print("execute_pending_signal pending_signal:", pending_signal)
    if pending_signal is None:
        return

    positions = get_open_positions()
    #print("execute_pending_signal Open positions:", positions)
    buy_exists = any(
        p.type == mt5.POSITION_TYPE_BUY
        for p in positions
    )

    sell_exists = any(
        p.type == mt5.POSITION_TYPE_SELL
        for p in positions
    )

    direction = pending_signal["direction"]
    #print("execute_pending_signal direction:", direction, "buy_exists:", buy_exists, "sell_exists:", sell_exists)
    if direction == "BUY" and buy_exists:
        pending_signal = None
        #print("execute_pending_signal: BUY signal ignored (position already open)")
        return

    if direction == "SELL" and sell_exists:
        pending_signal = None
        #print("execute_pending_signal: SELL signal ignored (position already open)")
        return

    sl = None

    if USE_STOPLOSS:
        sl = pending_signal["sl"]

    place_order(direction, sl)

    pending_signal = None





# ====================================

# MAIN LOOP

if __name__ == "__main__":

# ====================================
# MAIN LOOP
# ====================================
    print(f"DEBUG: trying to connect to MT5")

    last_bar_time = None

    connect_to_mt5()
    #print(f"DEBUG: Entering main loop with SYMBOL={SYMBOL}, TIMEFRAME={TIMEFRAME}, LOT_SIZE={LOT_SIZE}, HOLDING_HOURS={HOLDING_HOURS}")
    print_account_balance()

    while True:

        try:

            rates = mt5.copy_rates_from_pos(
                SYMBOL,
                TIMEFRAME,
                0,
                2
            )
            #print(rates)
            current_bar_time = rates[-1]["time"]
            

            if current_bar_time != last_bar_time:
                #print(f"DEBUG: fetched bar time={current_bar_time}, last_bar_time={last_bar_time}, pending_signal={pending_signal}")
                print(
                    datetime.now(),
                    "New Candle"
                )

                execute_pending_signal()

                check_signal()

                manage_exits()

                last_bar_time = current_bar_time

            sleep(5)

        except Exception as e:

            print("ERROR:", e)


            sleep(10)   