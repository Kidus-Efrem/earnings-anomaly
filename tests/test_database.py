import pytest
from unittest.mock import patch, MagicMock
from core.database import execute_query, get_db_connection

@patch("core.database.psycopg2.connect")
def test_get_db_connection(mock_connect):
    get_db_connection()
    assert mock_connect.called

@patch("core.database.get_db_connection")
def test_execute_query_fetch(mock_get_conn):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = [{"id": 1}]
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_get_conn.return_value = mock_conn

    res = execute_query("SELECT 1;", fetch=True)
    assert res == [{"id": 1}]
    mock_conn.commit.assert_called_once()
    mock_conn.close.assert_called_once()
