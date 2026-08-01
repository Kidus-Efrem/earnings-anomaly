"""initial_schema

Revision ID: 9d2eacd0224b
Revises: 
Create Date: 2026-07-29 11:19:03.679728

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d2eacd0224b'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('companies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(length=10), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('sector', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ticker')
    )
    op.create_table('transcripts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=True),
        sa.Column('call_date', sa.Date(), nullable=False),
        sa.Column('fiscal_quarter', sa.String(length=10), nullable=True),
        sa.Column('raw_html', sa.Text(), nullable=True),
        sa.Column('full_text', sa.Text(), nullable=True),
        sa.Column('qa_text', sa.Text(), nullable=True),
        sa.Column('qa_start_index', sa.Integer(), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('scraped_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('speakers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('transcript_id', sa.Integer(), sa.ForeignKey('transcripts.id'), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('role', sa.String(length=50), nullable=True),
        sa.Column('is_executive', sa.Boolean(), nullable=True),
        sa.Column('utterances', sa.ARRAY(sa.Text()), nullable=True),
        sa.Column('word_count', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('price_data',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=True),
        sa.Column('call_date', sa.Date(), nullable=False),
        sa.Column('price_1hr_before', sa.Numeric(), nullable=True),
        sa.Column('price_24hr_after', sa.Numeric(), nullable=True),
        sa.Column('price_48hr_after', sa.Numeric(), nullable=True),
        sa.Column('realized_vol_24hr', sa.Numeric(), nullable=True),
        sa.Column('realized_vol_48hr', sa.Numeric(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('anomaly_scores',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('transcript_id', sa.Integer(), sa.ForeignKey('transcripts.id'), nullable=True),
        sa.Column('drift_score', sa.Numeric(), nullable=True),
        sa.Column('ceo_drift_score', sa.Numeric(), nullable=True),
        sa.Column('cfo_drift_score', sa.Numeric(), nullable=True),
        sa.Column('analyst_hostility_score', sa.Numeric(), nullable=True),
        sa.Column('changepoint_minute', sa.Integer(), nullable=True),
        sa.Column('anomaly_rank', sa.Numeric(), nullable=True),
        sa.Column('computed_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('transcript_sentiment',
        sa.Column('ticker', sa.String(length=10), nullable=False),
        sa.Column('target_date', sa.Date(), nullable=False),
        sa.Column('positive_score', sa.Float(), nullable=True),
        sa.Column('negative_score', sa.Float(), nullable=True),
        sa.Column('neutral_score', sa.Float(), nullable=True),
        sa.Column('sentiment_polarity', sa.Float(), nullable=True),
        sa.Column('prepared_polarity', sa.Float(), nullable=True),
        sa.Column('qa_polarity', sa.Float(), nullable=True),
        sa.Column('divergence_score', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('ticker', 'target_date')
    )
    op.create_table('earnings_calendar',
        sa.Column('ticker', sa.String(length=10), nullable=False),
        sa.Column('target_date', sa.Date(), nullable=False),
        sa.Column('return_24h', sa.Float(), nullable=True),
        sa.Column('return_48h', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('ticker', 'target_date')
    )
    op.create_table('transcripts_content',
        sa.Column('ticker', sa.String(length=10), nullable=False),
        sa.Column('target_date', sa.Date(), nullable=False),
        sa.Column('prepared_text', sa.Text(), nullable=True),
        sa.Column('qa_text', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('ticker', 'target_date')
    )
    op.create_table('ingestion_jobs',
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.PrimaryKeyConstraint('job_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('ingestion_jobs')
    op.drop_table('transcripts_content')
    op.drop_table('earnings_calendar')
    op.drop_table('transcript_sentiment')
    op.drop_table('anomaly_scores')
    op.drop_table('price_data')
    op.drop_table('speakers')
    op.drop_table('transcripts')
    op.drop_table('companies')
