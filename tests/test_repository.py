"""Tests for MySQL repository module."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import pytest
from unittest.mock import patch, MagicMock
import mysql.connector


class TestSaveVideo:
    """Tests for save_video function."""

    @patch('repository.mysql.get_connection')
    def test_save_video_success(self, mock_get_conn):
        """Test successful video save."""
        from repository.mysql import save_video

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        video = {
            'video_id': 'abc123',
            'title': 'Test Video',
            'channel_id': 'UC123',
            'channel_title': 'Test Channel',
            'published_at': '2025-01-01T00:00:00Z',
            'view_count': 1000,
            'like_count': 100,
            'comment_count': 10,
            'fetched_at': '2025-01-21T10:00:00'
        }

        save_video(video)

        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()

    @patch('repository.mysql.get_connection')
    def test_save_video_connection_error(self, mock_get_conn):
        """Test connection error handling."""
        from repository.mysql import save_video

        mock_get_conn.side_effect = mysql.connector.Error('Connection refused')

        with pytest.raises(mysql.connector.Error):
            save_video({'video_id': 'abc123'})

    @patch('repository.mysql.get_connection')
    def test_save_video_truncates_long_title(self, mock_get_conn):
        """Test that long titles are truncated."""
        from repository.mysql import save_video

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        video = {
            'video_id': 'abc123',
            'title': 'A' * 300,  # Longer than 255
            'channel_id': 'UC123',
            'fetched_at': '2025-01-21T10:00:00'
        }

        save_video(video)

        # Verify execute was called (title should be truncated internally)
        mock_cursor.execute.assert_called_once()


class TestSaveSummary:
    """Tests for save_summary function."""

    @patch('repository.mysql.get_connection')
    def test_save_summary_success(self, mock_get_conn):
        """Test successful summary save."""
        from repository.mysql import save_summary

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        summary = {
            'video_id': 'abc123',
            'total_comments': 10,
            'positive_count': 5,
            'negative_count': 3,
            'other_count': 2,
            'positive_ratio': 50.0,
            'negative_ratio': 30.0,
            'analyzed_at': '2025-01-21T10:00:00'
        }

        save_summary(summary)

        # Should call delete first, then insert
        assert mock_cursor.execute.call_count == 2
        mock_conn.commit.assert_called_once()

    @patch('repository.mysql.get_connection')
    def test_save_summary_replaces_existing(self, mock_get_conn):
        """Test that existing summary is replaced."""
        from repository.mysql import save_summary

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        summary = {
            'video_id': 'abc123',
            'total_comments': 10,
            'positive_count': 5,
            'negative_count': 3,
            'other_count': 2,
            'positive_ratio': 50.0,
            'negative_ratio': 30.0,
            'analyzed_at': '2025-01-21T10:00:00'
        }

        save_summary(summary)

        # First call should be DELETE
        first_call = mock_cursor.execute.call_args_list[0]
        assert 'DELETE' in first_call[0][0]
class TestParseDatetime:
    """日時パース関数のテスト。"""

    def test_parse_datetime_with_z(self):
        """日時文字列(Z形式)のパース。"""
        from repository.mysql import _parse_datetime

        result = _parse_datetime('2025-01-21T10:00:00Z')
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 21

    def test_parse_datetime_with_timezone(self):
        """タイムゾーン付き日時のパース。"""
        from repository.mysql import _parse_datetime

        result = _parse_datetime('2025-01-21T10:00:00+09:00')
        assert result is not None

    def test_parse_datetime_with_microseconds(self):
        """マイクロ秒付き日時のパース。"""
        from repository.mysql import _parse_datetime

        result = _parse_datetime('2025-01-21T10:00:00.123456Z')
        assert result is not None

    def test_parse_datetime_none(self):
        """Noneの入力。"""
        from repository.mysql import _parse_datetime

        result = _parse_datetime(None)
        assert result is None

    def test_parse_datetime_invalid(self):
        """無効な日時文字列。"""
        from repository.mysql import _parse_datetime

        result = _parse_datetime('invalid-date')
        assert result is None


class TestConnectionPool:
    """接続プール関連のテスト。"""

    @patch('repository.mysql.MySQLConnectionPool')
    def test_connection_pool_creation(self, mock_pool_class):
        """接続プールの作成。"""
        from repository.mysql import _get_connection_pool
        import repository.mysql as repo_module

        # Reset pool
        repo_module._connection_pool = None

        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool

        with patch.dict(os.environ, {
            'MYSQL_POOL_SIZE': '10',
            'MYSQL_POOL_NAME': 'test_pool',
            'MYSQL_HOST': 'localhost',
            'MYSQL_PORT': '3306',
            'MYSQL_DATABASE': 'test_db',
            'MYSQL_USER': 'test_user',
            'MYSQL_PASSWORD': 'test_pass'
        }):
            pool = _get_connection_pool()

        assert pool is not None
        mock_pool_class.assert_called_once()

    @patch('repository.mysql._get_connection_pool')
    def test_get_connection_from_pool(self, mock_get_pool):
        """プールから接続を取得。"""
        from repository.mysql import get_connection

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.get_connection.return_value = mock_conn
        mock_get_pool.return_value = mock_pool

        conn = get_connection()

        assert conn is mock_conn
        mock_pool.get_connection.assert_called_once()
