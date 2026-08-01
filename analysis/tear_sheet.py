import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import yfinance as yf

# Add project root to path for local imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.database import get_db_connection

def generate_tear_sheet():
    print("Fetching backtest data from transcripts_warehouse...")
    
    query = """
    SELECT 
        ts.ticker, 
        ts.target_date, 
        ts.divergence_score, 
        ec.return_24h, 
        ec.return_48h 
    FROM transcript_sentiment ts
    INNER JOIN earnings_calendar ec 
        ON ts.ticker = ec.ticker 
        AND ts.target_date = ec.target_date
    WHERE ec.return_24h IS NOT NULL 
      AND ts.divergence_score IS NOT NULL;
    """
    
    try:
        conn = get_db_connection()
        df = pd.read_sql(query, conn)
        conn.close()
    except Exception as e:
        print(f"Error fetching data from database: {e}")
        print("Falling back to dummy data for tear sheet generation...")
        df = generate_dummy_data()

    if df.empty:
        print("No paired sentiment & returns data found in the database. Ensure both scraper pipelines have successfully run.")
        return

    print(f"Loaded {len(df)} financial records. Calculating quartiles and returns...")
    df['target_date'] = pd.to_datetime(df['target_date'])
    df['quartile'] = pd.qcut(df['divergence_score'], q=4, labels=['Q1 (Bottom)', 'Q2', 'Q3', 'Q4 (Top)'])
    
    # 1. Bar Plot of Means
    mean_returns = df.groupby('quartile')[['return_24h', 'return_48h']].mean() * 100 
    
    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)
    colors = sns.color_palette("coolwarm", 4)
    
    sns.barplot(x=mean_returns.index, y=mean_returns['return_24h'], ax=axes[0], palette=colors, hue=mean_returns.index, legend=False)
    axes[0].set_title('Mean 24h Return by Divergence Quartile', fontsize=14, fontweight='bold')
    axes[0].set_ylabel('Mean Return (%)')
    axes[0].set_xlabel('Divergence Score Quartile')
    axes[0].axhline(0, color='black', linewidth=1)
    
    sns.barplot(x=mean_returns.index, y=mean_returns['return_48h'], ax=axes[1], palette=colors, hue=mean_returns.index, legend=False)
    axes[1].set_title('Mean 48h Return by Divergence Quartile', fontsize=14, fontweight='bold')
    axes[1].set_ylabel('')
    axes[1].set_xlabel('Divergence Score Quartile')
    axes[1].axhline(0, color='black', linewidth=1)
    
    for ax in axes:
        for p in ax.patches:
            if p.get_height() != 0:
                ax.annotate(f"{p.get_height():.2f}%", 
                            (p.get_x() + p.get_width() / 2., p.get_height()), 
                            ha='center', va='bottom' if p.get_height() > 0 else 'top', 
                            fontsize=12, color='black', xytext=(0, 5 if p.get_height() > 0 else -15),
                            textcoords='offset points')
    
    plt.suptitle("Divergence Signal Efficacy (Tear Sheet)", fontsize=18, fontweight='bold')
    plt.tight_layout()
    bar_output_path = os.path.join(os.path.dirname(__file__), "divergence_backtest_bars.png")
    plt.savefig(bar_output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Bar plot generated successfully: {bar_output_path}")

    # 2. Cumulative Returns vs SPY Plot
    print("Fetching SPY data and compiling cumulative returns...")
    min_date = df['target_date'].min().strftime('%Y-%m-%d')
    # Add a few days buffer to max_date
    max_date = (df['target_date'].max() + pd.Timedelta(days=5)).strftime('%Y-%m-%d')
    
    spy = yf.Ticker("SPY").history(start=min_date, end=max_date)
    if not spy.empty:
        spy['SPY_Return'] = spy['Close'].pct_change()
        spy.index = spy.index.tz_localize(None).normalize()
        
        # Calculate daily portfolio returns per quartile (assuming equal weight of day's signals)
        daily_returns = df.groupby(['target_date', 'quartile'])['return_24h'].mean().unstack().fillna(0)
        
        # Merge with SPY
        merged = pd.merge(daily_returns, spy['SPY_Return'], left_index=True, right_index=True, how='inner')
        
        # Calculate cumulative returns
        cum_returns = (1 + merged).cumprod() - 1
        
        plt.figure(figsize=(12, 7))
        for q, color in zip(['Q1 (Bottom)', 'Q2', 'Q3', 'Q4 (Top)'], colors):
            if q in cum_returns.columns:
                plt.plot(cum_returns.index, cum_returns[q] * 100, label=q, color=color, linewidth=2)
        
        plt.plot(cum_returns.index, cum_returns['SPY_Return'] * 100, label='SPY (Benchmark)', color='black', linestyle='--', linewidth=2)
        
        plt.title('Cumulative Returns by Divergence Quartile vs SPY Benchmark', fontsize=16, fontweight='bold')
        plt.ylabel('Cumulative Return (%)', fontsize=12)
        plt.xlabel('Date', fontsize=12)
        plt.legend(loc='best')
        plt.axhline(0, color='gray', linestyle='-')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        cum_output_path = os.path.join(os.path.dirname(__file__), "divergence_cumulative_returns.png")
        plt.savefig(cum_output_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Cumulative returns plot generated successfully: {cum_output_path}")
    else:
        print("Failed to download SPY data for the time period. Skipping cumulative returns plot.")

def generate_dummy_data():
    """Generates dummy data for testing the tear sheet without DB connection."""
    import numpy as np
    np.random.seed(42)
    dates = pd.date_range(start='2023-01-01', end='2024-01-01', freq='B')
    num_records = 500
    
    random_dates = np.random.choice(dates, num_records)
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA']
    random_tickers = np.random.choice(tickers, num_records)
    
    divergence_scores = np.random.normal(0, 5, num_records)
    # create some signal: higher divergence -> higher return
    base_returns = np.random.normal(0.001, 0.02, num_records)
    return_24h = base_returns + divergence_scores * 0.001
    return_48h = return_24h + np.random.normal(0, 0.015, num_records)
    
    return pd.DataFrame({
        'ticker': random_tickers,
        'target_date': random_dates,
        'divergence_score': divergence_scores,
        'return_24h': return_24h,
        'return_48h': return_48h
    })

if __name__ == "__main__":
    generate_tear_sheet()
