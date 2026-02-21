"""Integration tests for the sentiment analysis pipeline.

These tests require Docker Compose services to be running.
Run with: docker compose exec app pytest tests/test_integration.py -v -m integration
"""

import sys
import os
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


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
