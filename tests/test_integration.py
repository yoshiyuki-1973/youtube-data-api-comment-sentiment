"""Integration tests for the sentiment analysis pipeline.

These tests require Docker Compose services to be running.
Run with: docker compose exec app pytest tests/test_integration.py -v -m integration
"""

import sys
import os
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


class TestDatabaseIntegration:
    """Integration tests for database operations."""

    @pytest.fixture
    def mock_db_env(self, monkeypatch):
        """Set up mock environment for DB testing."""
        monkeypatch.setenv('MYSQL_HOST', 'localhost')
        monkeypatch.setenv('MYSQL_PORT', '3306')
        monkeypatch.setenv('MYSQL_DATABASE', 'youtube_analytics_test')
        monkeypatch.setenv('MYSQL_USER', 'test_user')
        monkeypatch.setenv('MYSQL_PASSWORD', 'test_password')

    def test_save_and_get_video(self, mock_db_connection):
        """Test video UPSERT and retrieval."""
        from repository.mysql import save_video, get_video

        video_data = {
            'video_id': 'test123',
            'title': 'Test Video Title',
            'channel_id': 'UC123',
            'channel_title': 'Test Channel',
            'published_at': '2025-01-01T00:00:00Z',
            'view_count': 1000,
            'like_count': 100,
            'comment_count': 50,
            'fetched_at': datetime.now().isoformat()
        }

        # Mock cursor execute
        mock_cursor = mock_db_connection['cursor']
        mock_cursor.fetchone.return_value = video_data

        # Test save
        save_video(video_data)
        assert mock_cursor.execute.called

        # Test get
        result = get_video('test123')
        assert result is not None
        assert result['video_id'] == 'test123'

    def test_save_and_get_summary(self, mock_db_connection):
        """Test summary UPSERT and retrieval."""
        from repository.mysql import save_summary, get_summary

        summary_data = {
            'video_id': 'test123',
            'total_comments': 100,
            'positive_count': 60,
            'negative_count': 30,
            'other_count': 10,
            'positive_ratio': 0.6,
            'negative_ratio': 0.3,
            'analyzed_at': datetime.now().isoformat()
        }

        mock_cursor = mock_db_connection['cursor']
        mock_cursor.fetchone.return_value = summary_data

        # Test save
        save_summary(summary_data)
        assert mock_cursor.execute.called

        # Test get
        result = get_summary('test123')
        assert result is not None
        assert result['video_id'] == 'test123'

    def test_video_upsert_updates_existing(self, mock_db_connection):
        """Test that saving a video twice updates instead of duplicating."""
        from repository.mysql import save_video

        video_data = {
            'video_id': 'test123',
            'title': 'Original Title',
            'channel_id': 'UC123',
            'channel_title': 'Test Channel',
            'published_at': '2025-01-01T00:00:00Z',
            'view_count': 1000,
            'like_count': 100,
            'comment_count': 50,
            'fetched_at': datetime.now().isoformat()
        }

        mock_cursor = mock_db_connection['cursor']

        # First save
        save_video(video_data)

        # Update and save again
        video_data['title'] = 'Updated Title'
        video_data['view_count'] = 2000
        save_video(video_data)

        # Verify UPSERT SQL was used (ON DUPLICATE KEY UPDATE)
        calls = mock_cursor.execute.call_args_list
        for call in calls:
            sql = call[0][0]
            if 'INSERT INTO videos' in sql:
                assert 'ON DUPLICATE KEY UPDATE' in sql


class TestSentimentPipelineIntegration:
    """Integration tests for the sentiment analysis pipeline."""

    def test_full_pipeline_with_rules_fallback(self, sample_comments):
        """Test full pipeline with rules-only fallback mode."""
        from sentiment.analyzer import classify_comments, _classify_comment_rules_only
        from aggregate.summarizer import aggregate_video

        # Enable fallback mode
        with patch('sentiment.analyzer.FALLBACK_TO_RULES_ONLY', True):
            with patch('sentiment.analyzer.load_models'):
                with patch('sentiment.analyzer._ja_model_1', None):
                    with patch('sentiment.analyzer._ja_model_2', None):
                        with patch('sentiment.analyzer._multi_model', None):
                            # Classify comments using rules fallback
                            classified = classify_comments(sample_comments.copy())

                            assert len(classified) == 5
                            for comment in classified:
                                assert 'sentiment' in comment
                                assert isinstance(comment['sentiment'], dict)
                                assert 'positive' in comment['sentiment']
                                assert 'negative' in comment['sentiment']

                            # Aggregate results
                            video = {'video_id': 'test_video'}
                            summary = aggregate_video(video, classified)

                            assert summary['total_comments'] == 5
                            assert summary['positive_count'] + summary['negative_count'] + summary['other_count'] == 5

    def test_classify_comment_rules_only_function(self):
        """Test the rules-only classification function directly."""
        from sentiment.analyzer import _classify_comment_rules_only

        # Test positive text
        result = _classify_comment_rules_only('最高！素晴らしい！')
        assert result['positive'] > result['negative']
        assert result['language'] == 'ja'

        # Test negative text
        result = _classify_comment_rules_only('つまらない、最悪')
        assert result['negative'] > result['positive']
        assert result['language'] == 'ja'

        # Test empty text
        result = _classify_comment_rules_only('')
        assert result['language'] == 'unknown'

    def test_pipeline_flow_fetch_analyze_aggregate(self, sample_comments, sample_video):
        """Test the data flow: comments -> analyze -> aggregate."""
        from sentiment.analyzer import _classify_comment_rules_only
        from aggregate.summarizer import aggregate_video

        # Step 1: Simulate fetched comments (already have sample_comments)
        comments = sample_comments.copy()

        # Step 2: Classify with rules (for testing without models)
        for comment in comments:
            comment['sentiment'] = _classify_comment_rules_only(comment.get('text', ''))

        # Verify each comment has sentiment
        for comment in comments:
            assert 'sentiment' in comment
            sentiment = comment['sentiment']
            assert all(k in sentiment for k in ['positive', 'negative', 'neutral'])

        # Step 3: Aggregate
        summary = aggregate_video(sample_video, comments)

        assert summary['video_id'] == sample_video['video_id']
        assert summary['total_comments'] == len(comments)
        assert 'positive_count' in summary
        assert 'negative_count' in summary
        assert 'other_count' in summary
        assert 'analyzed_at' in summary


class TestJSONCacheIntegration:
    """Integration tests for JSON cache functionality."""

    @pytest.fixture
    def temp_json_dir(self):
        """Create a temporary directory for JSON cache testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_write_and_read_json_cache(self, temp_json_dir, sample_video, sample_comments):
        """Test writing and reading JSON cache files."""
        video_id = sample_video['video_id']
        cache_file = temp_json_dir / f'{video_id}.json'

        # Create cache data
        cache_data = {
            'video': sample_video,
            'comments': sample_comments,
            'fetched_at': datetime.now().isoformat()
        }

        # Write cache
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)

        assert cache_file.exists()

        # Read cache
        with open(cache_file, 'r', encoding='utf-8') as f:
            loaded = json.load(f)

        assert loaded['video']['video_id'] == video_id
        assert len(loaded['comments']) == len(sample_comments)

    def test_json_cache_with_utf8mb4_characters(self, temp_json_dir):
        """Test JSON cache handles UTF-8 MB4 (emoji) correctly."""
        cache_file = temp_json_dir / 'emoji_test.json'

        data = {
            'video_id': 'emoji123',
            'title': '絵文字テスト 🎉✨💖',
            'comments': [
                {'text': '最高！👍', 'sentiment': {'positive': 0.9, 'negative': 0.05, 'neutral': 0.05}},
                {'text': '😡💢', 'sentiment': {'positive': 0.1, 'negative': 0.8, 'neutral': 0.1}},
            ]
        }

        # Write
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Read
        with open(cache_file, 'r', encoding='utf-8') as f:
            loaded = json.load(f)

        assert '🎉' in loaded['title']
        assert '👍' in loaded['comments'][0]['text']
        assert '😡' in loaded['comments'][1]['text']

    def test_json_cache_directory_structure(self, temp_json_dir):
        """Test creating cache in nested directory structure."""
        nested_dir = temp_json_dir / 'data' / 'json'
        nested_dir.mkdir(parents=True, exist_ok=True)

        cache_file = nested_dir / 'test_video.json'
        cache_file.write_text('{"test": true}', encoding='utf-8')

        assert cache_file.exists()
        assert json.loads(cache_file.read_text())['test'] is True


class TestFallbackModeIntegration:
    """Integration tests for fallback mode behavior."""

    def test_fallback_mode_enabled_with_env_var(self, monkeypatch):
        """Test that FALLBACK_TO_RULES_ONLY env var enables fallback."""
        monkeypatch.setenv('FALLBACK_TO_RULES_ONLY', 'true')

        # Re-import to pick up env var change
        import importlib
        from sentiment import analyzer
        importlib.reload(analyzer)

        assert analyzer.FALLBACK_TO_RULES_ONLY is True

        # Clean up
        monkeypatch.delenv('FALLBACK_TO_RULES_ONLY', raising=False)
        importlib.reload(analyzer)

    def test_fallback_mode_disabled_by_default(self, monkeypatch):
        """Test that fallback mode is disabled by default."""
        monkeypatch.delenv('FALLBACK_TO_RULES_ONLY', raising=False)

        import importlib
        from sentiment import analyzer
        importlib.reload(analyzer)

        assert analyzer.FALLBACK_TO_RULES_ONLY is False

    def test_classify_comments_uses_fallback_when_models_fail(self, sample_comments):
        """Test that classify_comments uses fallback when all models fail."""
        from sentiment.analyzer import classify_comments

        comments = sample_comments.copy()

        with patch('sentiment.analyzer.FALLBACK_TO_RULES_ONLY', True):
            with patch('sentiment.analyzer.load_models'):
                with patch('sentiment.analyzer._ja_model_1', None):
                    with patch('sentiment.analyzer._ja_model_2', None):
                        with patch('sentiment.analyzer._multi_model', None):
                            result = classify_comments(comments)

                            # Should not raise, should return classified comments
                            assert len(result) == len(comments)
                            for comment in result:
                                assert 'sentiment' in comment

    def test_classify_comments_raises_without_fallback(self, sample_comments):
        """Test that classify_comments raises when models fail and fallback disabled."""
        from sentiment.analyzer import classify_comments

        comments = sample_comments.copy()

        with patch('sentiment.analyzer.FALLBACK_TO_RULES_ONLY', False):
            with patch('sentiment.analyzer.load_models'):
                with patch('sentiment.analyzer._ja_model_1', None):
                    with patch('sentiment.analyzer._ja_model_2', None):
                        with patch('sentiment.analyzer._multi_model', None):
                            with pytest.raises(RuntimeError, match='全ての感情分析モデルのロード'):
                                classify_comments(comments)


class TestEndToEndFlow:
    """End-to-end flow tests."""

    def test_complete_analysis_flow_mocked(
        self, sample_video, sample_comments, mock_db_connection
    ):
        """Test complete flow from input to DB save (mocked)."""
        from sentiment.analyzer import _classify_comment_rules_only
        from aggregate.summarizer import aggregate_video
        from repository.mysql import save_video, save_summary

        # Step 1: Simulate video and comments already fetched
        video = sample_video.copy()
        comments = sample_comments.copy()

        # Step 2: Classify comments
        for comment in comments:
            comment['sentiment'] = _classify_comment_rules_only(comment.get('text', ''))

        # Step 3: Aggregate
        summary = aggregate_video(video, comments)

        # Step 4: Save to DB (mocked)
        save_video(video)
        save_summary(summary)

        # Verify DB operations were called
        mock_cursor = mock_db_connection['cursor']
        assert mock_cursor.execute.called
        assert mock_db_connection['connection'].commit.called

    def test_analysis_preserves_comment_metadata(self, sample_comments):
        """Test that analysis preserves original comment metadata."""
        from sentiment.analyzer import _classify_comment_rules_only

        comments = sample_comments.copy()
        original_ids = [c['comment_id'] for c in comments]
        original_authors = [c['author'] for c in comments]
        original_texts = [c['text'] for c in comments]

        # Classify
        for comment in comments:
            comment['sentiment'] = _classify_comment_rules_only(comment.get('text', ''))

        # Verify metadata preserved
        for i, comment in enumerate(comments):
            assert comment['comment_id'] == original_ids[i]
            assert comment['author'] == original_authors[i]
            assert comment['text'] == original_texts[i]
            assert 'sentiment' in comment
