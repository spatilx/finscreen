import streamlit as st
import pandas as pd
import time
from massive import RESTClient   # ← Updated import
from datetime import datetime, timedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="Sugar Babies Scanner", layout="wide", page_icon="🍭")
st.title("🍭 Sugar Babies (SB Setup) Scanner")
st.markdown("**Dynamic Momentum Scanner** — Repeated 4%+ moves on 9M+ volume")

# ================== SIDEBAR ==================
st.sidebar.header("Scan Settings")
MIN_PRICE = st.sidebar.slider("Minimum Price ($)", 1.0, 20.0, 2.0)
MIN_AVG_VOLUME = st.sidebar.number_input("Minimum Avg Daily Volume", 100000, 5000000, 500000)
MAX_TICKERS = st.sidebar.slider("Max Tickers to Scan", 500, 5000, 2000)

st.sidebar.header("Email Notification")
ENABLE_EMAIL = st.sidebar.checkbox("Send email when scan completes", value=True)
RECIPIENT_EMAIL = st.sidebar.text_input("Recipient Email", value="your@email.com")

RUN_SCAN = st.sidebar.button("🚀 Run Fresh Scan", type="primary")

# ================== SECRETS ==================
MASSIVE_API_KEY = st.secrets.get("MASSIVE_API_KEY")   # ← Updated key name
GMAIL_SENDER = st.secrets.get("GMAIL_SENDER")
GMAIL_APP_PASSWORD = st.secrets.get("GMAIL_APP_PASSWORD")

if not MASSIVE_API_KEY:
    st.error("Add MASSIVE_API_KEY in Streamlit Secrets")
    st.stop()

LOOKBACKS = [1450, 1260, 1008, 756, 504, 252, 126, 50, 20, 10, 5]

# ================== HELPER FUNCTIONS ==================
@st.cache_data(ttl=86400)
def get_active_tickers(client, max_tickers):
    tickers = []
    for t in client.list_tickers(market="stocks", active=True, limit=1000):
        if len(tickers) >= max_tickers:
            break
        if t.ticker and t.ticker.isalpha():
            tickers.append(t.ticker)
    return tickers

def count_high_volume_momentum(aggs, lookback):
    if len(aggs) < lookback:
        return 0
    df = pd.DataFrame(aggs).tail(lookback)
    condition = (
        (df['close'] / df['close'].shift(1) >= 1.04) &
        (df['volume'] > df['volume'].shift(1)) &
        (df['volume'] >= 8900000)
    )
    return int(condition.sum())

def send_scan_email(df, recipient):
    if not GMAIL_SENDER or not GMAIL_APP_PASSWORD:
        st.warning("Email credentials not configured.")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_SENDER
        msg['To'] = recipient
        msg['Subject'] = f"Sugar Babies Scan Complete - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        body = f"""
        Sugar Babies (SB Setup) Scan Results
        
        Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}
        Stocks Found: {len(df)}
        Top 10 Stocks: {', '.join(df['Ticker'].head(10).tolist())}
        
        Full list attached.
        """
        msg.attach(MIMEText(body, 'plain'))

        csv_bytes = df.to_csv(index=False).encode('utf-8')
        attachment = MIMEApplication(csv_bytes, _subtype="csv")
        attachment.add_header('Content-Disposition', 'attachment', 
                            filename=f"sugar_babies_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
        msg.attach(attachment)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Failed to send email: {str(e)}")
        return False

# ================== MAIN SCAN LOGIC ==================
if RUN_SCAN:
    client = RESTClient(api_key=MASSIVE_API_KEY)   # ← Updated client usage
    
    with st.spinner("Fetching tickers..."):
        tickers = get_active_tickers(client, MAX_TICKERS)
        st.info(f"Scanning **{len(tickers)}** stocks...")

    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, ticker in enumerate(tickers):
        status_text.text(f"Processing {ticker} ({i+1}/{len(tickers)})")
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=2555)

            aggs = list(client.get_aggs(
                ticker, 1, "day", 
                from_=start_date.strftime("%Y-%m-%d"),
                to=end_date.strftime("%Y-%m-%d"),
                limit=50000
            ))

            if len(aggs) < 150:
                continue

            df_agg = pd.DataFrame(aggs)
            avg_vol = df_agg['volume'].mean()
            
            if avg_vol < MIN_AVG_VOLUME:
                continue
            current_price = df_agg['close'].iloc[-1]
            if current_price < MIN_PRICE:
                continue

            counts = {f"count_{lb}": count_high_volume_momentum(aggs, lb) for lb in LOOKBACKS}

            results.append({
                'Ticker': ticker,
                'Price': round(current_price, 2),
                'AvgVolume': int(avg_vol),
                **counts
            })

        except:
            continue

        progress_bar.progress(min((i + 1) / len(tickers), 1.0))
        time.sleep(0.25)

    if results:
        df = pd.DataFrame(results)
        sort_cols = [f"count_{lb}" for lb in sorted(LOOKBACKS, reverse=True)]
        df = df.sort_values(by=sort_cols, ascending=False)

        final_cols = ['Ticker', 'Price', 'AvgVolume'] + [f"count_{lb}" for lb in LOOKBACKS]
        df = df[final_cols]

        st.success(f"✅ Scan Complete! **{len(df)}** stocks found.")

        st.subheader("Top 100 Sugar Babies")
        st.dataframe(df.head(100), use_container_width=True, hide_index=True)

        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", csv, f"sugar_babies_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")

        if ENABLE_EMAIL and RECIPIENT_EMAIL:
            with st.spinner("Sending email..."):
                if send_scan_email(df, RECIPIENT_EMAIL):
                    st.success(f"📧 Email sent to **{RECIPIENT_EMAIL}**!")

        st.session_state['last_scan'] = df
    else:
        st.error("No stocks matched your criteria.")

elif 'last_scan' in st.session_state:
    st.subheader("Previous Scan Results")
    st.dataframe(st.session_state['last_scan'].head(100), use_container_width=True, hide_index=True)

st.caption("Powered by Massive.com (formerly Polygon.io)")
