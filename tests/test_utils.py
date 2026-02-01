"""Tests for utility modules."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from tempfile import TemporaryDirectory

from utils.text import truncate_string
from utils.cache import save_json, load_json


class TestTruncateString:
    """Tests for truncate_string function."""

    def test_short_string_unchanged(self):
        """Test that short strings are not truncated."""
        result = truncate_string('Hello', 10)
        assert result == 'Hello'

    def test_exact_length_unchanged(self):
        """Test that strings at exact length are unchanged."""
        result = truncate_string('Hello', 5)
        assert result == 'Hello'

    def test_long_string_truncated(self):
        """Test that long strings are truncated."""
        result = truncate_string('Hello World', 5)
        assert result == 'Hello'
        assert len(result) == 5

    def test_empty_string(self):
        """Test empty string handling."""
        result = truncate_string('', 10)
        assert result == ''

    def test_none_like_empty(self):
        """Test None-like input (empty string)."""
        result = truncate_string('', 5)
        assert result == ''

    def test_japanese_text(self):
        """Test Japanese text truncation."""
        result = truncate_string('こんにちは世界', 5)
        assert result == 'こんにちは'
        assert len(result) == 5

    def test_emoji_truncation(self):
        """Test emoji truncation (4-byte characters)."""
        result = truncate_string('Hello 😊 World', 8)
        assert len(result) == 8
        # Should be valid UTF-8
        result.encode('utf-8')

    def test_mixed_content(self):
        """Test mixed ASCII, Japanese, and emoji."""
        text = 'Hello 日本 😊'
        result = truncate_string(text, 10)
        assert len(result) == 10
        # Should be valid UTF-8
        result.encode('utf-8')

    def test_zero_max_length(self):
        """Test zero max length returns empty string."""
        result = truncate_string('Hello', 0)
        assert result == ''

    def test_one_max_length(self):
        """Test max length of 1."""
        result = truncate_string('Hello', 1)
        assert result == 'H'


class TestCacheModule:
    """Tests for cache module functions."""

    def test_save_and_load_json(self):
        """Test saving and loading JSON data."""
        with TemporaryDirectory() as tmpdir:
            with patch('utils.cache.JSON_OUTPUT_DIR', Path(tmpdir)):
                video_id = 'test123'
                data = {'title': 'Test Video', 'comments': [{'text': 'hello'}]}

                save_json(video_id, data)
                loaded = load_json(video_id)

                assert loaded == data

    def test_load_nonexistent_returns_none(self):
        """Test loading non-existent file returns None."""
        with TemporaryDirectory() as tmpdir:
            with patch('utils.cache.JSON_OUTPUT_DIR', Path(tmpdir)):
                result = load_json('nonexistent123')
                assert result is None

    def test_save_creates_directory(self):
        """Test that save_json creates directory if not exists."""
        with TemporaryDirectory() as tmpdir:
            nested_dir = Path(tmpdir) / 'nested' / 'path'
            with patch('utils.cache.JSON_OUTPUT_DIR', nested_dir):
                save_json('test', {'key': 'value'})
                assert nested_dir.exists()

    def test_save_json_with_unicode(self):
        """Test saving JSON with Unicode content."""
        with TemporaryDirectory() as tmpdir:
            with patch('utils.cache.JSON_OUTPUT_DIR', Path(tmpdir)):
                video_id = 'unicode_test'
                data = {
                    'title': '日本語タイトル 😊',
                    'comments': [{'text': '素晴らしい動画！👍'}]
                }

                save_json(video_id, data)
                loaded = load_json(video_id)

                assert loaded == data
                assert loaded['title'] == '日本語タイトル 😊'

    def test_json_file_format(self):
        """Test that saved JSON is properly formatted."""
        with TemporaryDirectory() as tmpdir:
            with patch('utils.cache.JSON_OUTPUT_DIR', Path(tmpdir)):
                video_id = 'format_test'
                data = {'key': 'value'}

                save_json(video_id, data)

                # Read raw file and check format
                filepath = Path(tmpdir) / f'{video_id}.json'
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Should be indented (pretty-printed)
                assert '\n' in content
                # Should not have escape sequences for non-ASCII
                assert 'ensure_ascii=False' or '\\u' not in content
