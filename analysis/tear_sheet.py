import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

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
    
    conn = get_db_connection()
    df = pd.read_sql(query, conn)
    conn.close()

    if df.empty:
        print("No paired sentiment & returns data found in the database. Ensure both scraper pipelines have successfully run.")
        return

    print(f"Loaded {len(df)} financial records. Calculating quantiles...")

    # Define quartiles for the divergence score
    # High divergence score indicates positive asymmetry between prepared remarks and Q&A
    df['quartile'] = pd.qcut(df['divergence_score'], q=4, labels=['Q1 (Bottom)', 'Q2', 'Q3', 'Q4 (Top)'])
    
    # Calculate means
    mean_returns = df.groupby('quartile')[['return_24h', 'return_48h']].mean() * 100 # Convert to percentage
    
    # Plotting
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
    
    # Add annotations
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
    
    output_path = os.path.join(os.path.dirname(__file__), "divergence_backtest.png")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Tear sheet generated successfully: {output_path}")

if __name__ == "__main__":
    generate_tear_sheet()
