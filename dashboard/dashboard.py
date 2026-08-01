import streamlit as st
import pandas as pd
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.database import get_db_connection

st.set_page_config(page_title="Earnings Anomaly", layout="wide")
st.title("Earnings Anomaly Dashboard")

@st.cache_data
def load_data():
    query = """
    SELECT ts.ticker, ts.target_date, ts.divergence_score, ec.return_24h, ec.return_48h 
    FROM transcript_sentiment ts
    INNER JOIN earnings_calendar ec ON ts.ticker = ec.ticker AND ts.target_date = ec.target_date
    ORDER BY ts.target_date DESC LIMIT 100;
    """
    try:
        conn = get_db_connection()
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.warning(f"Database connection failed: {e}. Serving dummy data...")
        import numpy as np
        dates = pd.date_range(start='2023-01-01', end='2024-01-01', freq='B')
        return pd.DataFrame({
            "ticker": np.random.choice(['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META'], 100),
            "target_date": np.random.choice(dates, 100),
            "divergence_score": np.random.normal(0, 5, 100),
            "return_24h": np.random.normal(0, 0.02, 100)
        })

df = load_data()

st.subheader("Recent Transcripts & Signals")
st.dataframe(df.style.background_gradient(cmap="coolwarm", subset=["divergence_score", "return_24h"]), use_container_width=True)

col1, col2 = st.columns(2)
with col1:
    st.subheader("Divergence vs Tickers (Top 20)")
    st.bar_chart(df.head(20).set_index('ticker')['divergence_score'])
with col2:
    st.subheader("24h Price Returns")
    st.scatter_chart(df, x='divergence_score', y='return_24h')
