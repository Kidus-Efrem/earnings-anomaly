import sys
import os
import pandas as pd
from scipy import stats

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scraper.postgres_db import get_pg_connection

def validate_divergence_signal():
    conn = get_pg_connection()

    print("📊 Fetching joined data for validation...")
    query = """
        SELECT
            ts.ticker,
            ts.target_date,
            ts.prepared_polarity,
            ts.qa_polarity,
            ts.divergence_score,
            ec.car_24h,
            ec.car_48h
        FROM transcript_sentiment ts
        JOIN earnings_calendar ec
            ON ts.ticker = ec.ticker AND ts.target_date = ec.target_date
        WHERE ts.divergence_score IS NOT NULL
          AND ec.car_24h IS NOT NULL;
    """
    df = pd.read_sql(query, conn)
    conn.close()

    if df.empty:
        print("❌ No data found. Check database.")
        return

    print(f"✅ Loaded {len(df)} valid records with Divergence Scores and CAR.\n")

    # ==========================================
    # 1. SPEARMAN RANK CORRELATION
    # ==========================================
    print("🔬 Statistical Validation (Spearman Rank Correlation):")
    print("(Testing if Divergence Score correlates with Market-Adjusted Returns)\n")

    r_24h, p_24h = stats.spearmanr(df['divergence_score'], df['car_24h'])
    print(f"24h CAR  | Spearman r = {r_24h:.4f} | p-value = {p_24h:.4f} | n = {len(df)}")

    r_48h, p_48h = stats.spearmanr(df['divergence_score'], df['car_48h'])
    print(f"48h CAR  | Spearman r = {r_48h:.4f} | p-value = {p_48h:.4f} | n = {len(df)}")

    # ==========================================
    # 2. QUARTILE ANALYSIS (Sanity Check)
    # ==========================================
    print("\n📊 Quartile Analysis (Divergence Score vs 48h CAR):")
    print("Note: Divergence = Prepared Polarity - Q&A Polarity")
    print("High Positive Divergence = Upbeat Script, Defensive Q&A (Potentially Bearish)")
    print("High Negative Divergence = Cautious Script, Confident Q&A (Potentially Bullish)\n")

    # Sort from most negative divergence (Q1) to most positive divergence (Q4)
    df['divergence_quartile'] = pd.qcut(
        df['divergence_score'],
        4,
        labels=['Q1 (Most Negative Div)', 'Q2', 'Q3', 'Q4 (Most Positive Div)']
    )

    quartile_means = df.groupby('divergence_quartile')['car_48h'].mean()
    print(quartile_means)

    # Calculate the spread between Q1 and Q4
    spread = quartile_means.iloc[0] - quartile_means.iloc[-1]
    print(f"\n📈 Q1 to Q4 Spread: {spread * 100:.2f}% (in decimal: {spread:.4f})")

    # ==========================================
    # 3. THE VERDICT
    # ==========================================
    print("\n" + "="*60)
    if p_48h < 0.05:
        print("🟢 VERDICT: STATISTICALLY SIGNIFICANT SIGNAL (p < 0.05)")
        print("   The divergence between scripted remarks and unscripted Q&A")
        print("   reliably predicts market-adjusted stock returns.")
        print("   -> WE HAVE A GREEN LIGHT TO BUILD THE REAL-TIME API.")
    else:
        print("🟡 VERDICT: SIGNAL IS WEAK OR NOISY (p > 0.05)")
        print("   The divergence score alone may not be enough.")
        print("   -> We may need to add company-level Z-score normalization")
        print("      or combine it with fundamental EPS surprises before building the API.")
    print("="*60)

if __name__ == "__main__":
    validate_divergence_signal()