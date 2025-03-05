from flask import Flask, jsonify, request, send_from_directory
from datetime import datetime, timedelta
from flask_cors import CORS
import pandas as pd
import ccxt
import yfinance as yf
import numpy as np
import random
import os

app = Flask(__name__, static_folder='.')
CORS(app, resources={r"/*": {"origins": "*"}})

def get_next_candle_time(timeframe):
    now = datetime.now()
    if timeframe == '1m':
        return (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
    elif timeframe == '5m':
        next_minute = (now.minute // 5 * 5) + 5
        return now.replace(minute=next_minute % 60, 
                         hour=now.hour + (next_minute // 60), 
                         second=0, microsecond=0)
    elif timeframe == '15m':
        next_minute = (now.minute // 15 * 15) + 15
        return now.replace(minute=next_minute % 60,
                         hour=now.hour + (next_minute // 60),
                         second=0, microsecond=0)
    return now

def generate_random_strength():
    strength = random.randint(0, 100)
    if strength < 30:
        strength = random.randint(0, 33)
    elif strength < 70:
        strength = random.randint(34, 66)
    else:
        strength = random.randint(67, 100)
    return strength

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/signal', methods=['GET'])
def get_signal():
    symbol = request.args.get('symbol', 'BTCUSD').replace("/", "").upper()
    timeframe = request.args.get('timeframe', '5m').lower().replace(" ", "").replace("minuto", "m").replace("minutos", "m")
    
    try:
        if timeframe not in ['1m', '5m', '15m']:
            raise ValueError("Timeframe inválido")

        next_candle_time = get_next_candle_time(timeframe)
        next_candle = next_candle_time.strftime("%H:%M")
        
        if any(s in symbol for s in ["EUR","GBP","USD","AUD","NZD"]):
            ticker = yf.Ticker(f"{symbol}=X")
            df = ticker.history(period="3d", interval=timeframe).reset_index()
            df['timestamp'] = pd.to_datetime(df['Datetime']).astype('int64') // 10**9
            df.rename(columns={'Open':'open', 'High':'high', 'Low':'low', 'Close':'close'}, inplace=True)
        else:
            exchange = ccxt.binance()
            ohlcv = exchange.fetch_ohlcv(f"{symbol}/USDT", timeframe, limit=100)
            df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
        
        df['sma20'] = df['close'].rolling(20).mean()
        delta = df['close'].diff()
        avg_gain = delta.clip(lower=0).rolling(14).mean()
        avg_loss = (-delta.clip(upper=0)).rolling(14).mean().replace(0, 0.0001)
        rs = avg_gain / avg_loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        last_close = df['close'].iloc[-1]
        sma20 = df['sma20'].iloc[-1]

        if last_close > sma20:
            direction = "COMPRA"
            hue = 120
        else:
            direction = "VENDA"
            hue = 0

        strength = generate_random_strength()

        return jsonify({
            "status": "success",
            "signal": direction,
            "next_candle": next_candle,
            "color": f"hsl({hue}, 100%, 50%)",
            "strength": strength
        })
        
    except Exception as e:
        print(f"Erro: {str(e)}")
        return jsonify({
            "status": "success",
            "signal": "SINAL NEUTRO",
            "next_candle": datetime.now().strftime("%H:%M"),
            "color": "#808080",
            "strength": 50
        })

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)