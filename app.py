import streamlit as st
import pandas as pd
import yfinance as yf
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="Stockbee Sugar Babies Scanner", layout="wide")
st.title("🍭 Sugar Babies (SB Setup) Scanner")
st.markdown("**Momentum stocks with repeated 4%+ moves on 9M+ volume days**")

# Config
LOOKBACKS = [1450, 1260, 1008, 756, 504, 252, 126, 50, 20, 10, 5]
MIN_PRICE = st.sidebar.slider("Min Price", 1.0, 10.0, 2.0)
MIN_AVG_VOL = st.sidebar.number_input("Min Avg Volume", 100_000, 2_000_000, 500_000)

def count_high_volume_momentum(df, lookback):
    if len(df) < lookback or df.empty:
        return 0
    df = df.tail(lookback).copy()
    condition = (
        (df['Close'] / df['Close'].shift(1) >= 1.04) &
        (df['Volume'] > df['Volume'].shift(1)) &
        (df['Volume'] >= 8_900_000)
    )
    return int(condition.sum())

if st.button("🚀 Run Fresh Scan (this may take 5-15 mins)", type="primary"):
    with st.spinner("Downloading data and scanning..."):
        # Get tickers
        url = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/all/all_tickers.txt"
        tickers = pd.read_csv(url, header=None)[0].tolist()[:3000]  # Limit for cloud speed
        
        results = []
        progress_bar = st.progress(0)
        
        for i, ticker in enumerate(tqdm(tickers)):
            try:
                data = yf.download(ticker, period="max", progress=False, auto_adjust=True)
                if len(data) < 100 or data['Volume'].mean() < MIN_AVG_VOL:
                    continue
                price = data['Close'].iloc[-1]
                if price < MIN_PRICE:
                    continue
                
                counts = {f"count_{lb}": count_high_volume_momentum(data, lb) for lb in LOOKBACKS}
                
                results.append({
                    'Ticker': ticker,
                    'Price': round(price, 2),
                    'AvgVolume': int(data['Volume'].mean()),
                    **counts
                })
            except:
                continue
            
            progress_bar.progress(min((i+1)/len(tickers), 1.0))
        
        df = pd.DataFrame(results)
        sort_cols = [f"count_{lb}" for lb in sorted(LOOKBACKS, reverse=True)]
        df = df.sort_values(by=sort_cols, ascending=False)
        
        cols = ['Ticker', 'Price', 'AvgVolume'] + [f"count_{lb}" for lb in LOOKBACKS]
        df = df[cols]
        
        st.success(f"Scan complete! Found {len(df)} stocks.")
        st.dataframe(df.head(100), use_container_width=True)
        
        csv = df.to_csv(index=False).encode()
        st.download_button("📥 Download Full CSV", csv, "sugar_babies_watchlist.csv", "text/csv")

# Display last run info or cached results if you implement caching
st.info("💡 For faster runs, consider using Polygon.io API instead of yfinance.")
