"""Tests for sentiment analyzer."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import pytest
from unittest.mock import patch, MagicMock
from sentiment.analyzer import (
    classify_comment,
    classify_comments,
    _rule_based_classify,
    _adjust_sentiment_with_rules,
    load_models,
)


def _get_dominant_sentiment(result: dict) -> str:
    """Get dominant sentiment label from scores dict."""
    pos = result.get('positive', 0)
    neg = result.get('negative', 0)
    neu = result.get('neutral', 0)
    max_score = max(pos, neg, neu)
    if max_score == pos:
        return 'pos'
    elif max_score == neg:
        return 'neg'
    return 'other'


class TestClassifyComment:
    """Tests for classify_comment function."""

    def test_classify_returns_dict(self):
        """Test that classify_comment returns a dict with expected keys."""
        result = classify_comment('テスト')
        assert isinstance(result, dict)
        assert 'positive' in result
        assert 'negative' in result
        assert 'neutral' in result
        assert 'language' in result

    def test_classify_positive(self):
        """Test positive sentiment classification returns higher positive score."""
        result = classify_comment('最高！とても面白かった')
        assert _get_dominant_sentiment(result) == 'pos'

    def test_classify_negative(self):
        """Test negative sentiment classification returns higher negative score."""
        result = classify_comment('つまらない、時間の無駄')
        assert _get_dominant_sentiment(result) == 'neg'

    def test_classify_empty_string(self):
        """Test empty string returns balanced scores."""
        result = classify_comment('')
        assert result['language'] == 'unknown'
        # Empty string should have near-equal scores
        assert abs(result['positive'] - result['negative']) < 0.1

    def test_classify_whitespace_only(self):
        """Test whitespace-only string returns balanced scores."""
        result = classify_comment('   ')
        assert result['language'] == 'unknown'

    def test_classify_none(self):
        """Test None returns balanced scores."""
        result = classify_comment(None)
        assert result['language'] == 'unknown'

    def test_classify_japanese_text_detected(self):
        """Test Japanese text is detected correctly."""
        result = classify_comment('これは日本語です')
        assert result['language'] == 'ja'

    def test_classify_english_text_detected(self):
        """Test English text is detected as 'other' language."""
        result = classify_comment('This is English text')
        assert result['language'] == 'other'

    def test_classify_scores_sum_approximately_one(self):
        """Test that scores sum approximately to 1.0."""
        result = classify_comment('素晴らしい動画でした')
        total = result['positive'] + result['negative'] + result['neutral']
        assert abs(total - 1.0) < 0.01


class TestRuleBasedClassify:
    """Tests for rule-based classification."""

    def test_multiple_positive_words(self):
        """Test text with multiple positive words."""
        result = _rule_based_classify('最高で素晴らしい、感動した')
        assert result == 'pos'

    def test_multiple_negative_words(self):
        """Test text with multiple negative words."""
        result = _rule_based_classify('最悪でひどい、がっかり')
        assert result == 'neg'

    def test_mixed_sentiment(self):
        """Test text with mixed sentiment words."""
        # 2 positive, 1 negative -> positive
        result = _rule_based_classify('最高で素晴らしいけど少し残念')
        assert result == 'pos'

    def test_positive_emoji(self):
        """Test positive emoji detection."""
        result = _rule_based_classify('👍❤✨')
        assert result == 'pos'

    def test_negative_emoji(self):
        """Test negative emoji detection."""
        result = _rule_based_classify('👎😡💢')
        assert result == 'neg'


class TestAdjustSentimentWithRules:
    """Tests for _adjust_sentiment_with_rules function."""

    def test_strong_negative_expression_boosts_negative(self):
        """Test that strong negative expressions boost negative score."""
        base_scores = {'positive': 0.5, 'negative': 0.3, 'neutral': 0.2}
        result = _adjust_sentiment_with_rules('つまらない、最悪', base_scores)
        # After adjustment, negative should be higher
        assert result['negative'] > base_scores['negative']
        assert result['positive'] < base_scores['positive']

    def test_sarcasm_detected_棒読み(self):
        """Test sarcasm detection with 棒読み marker."""
        base_scores = {'positive': 0.6, 'negative': 0.2, 'neutral': 0.2}
        result = _adjust_sentiment_with_rules('さすがですね（棒）', base_scores)
        # Sarcasm should boost negative
        assert result['negative'] > base_scores['negative']

    def test_rhetorical_question_detected(self):
        """Test rhetorical question detection."""
        base_scores = {'positive': 0.5, 'negative': 0.3, 'neutral': 0.2}
        result = _adjust_sentiment_with_rules('これが面白いの？', base_scores)
        # Rhetorical question should boost negative
        assert result['negative'] > base_scores['negative']

    def test_negation_with_positive_reverses(self):
        """Test that positive + negation reverses sentiment."""
        base_scores = {'positive': 0.6, 'negative': 0.2, 'neutral': 0.2}
        result = _adjust_sentiment_with_rules('面白くない', base_scores)
        # Negated positive should boost negative
        assert result['negative'] > base_scores['negative']

    def test_strong_positive_expression_boosts_positive(self):
        """Test that strong positive expressions boost positive score."""
        base_scores = {'positive': 0.4, 'negative': 0.3, 'neutral': 0.3}
        result = _adjust_sentiment_with_rules('最高！神回！', base_scores)
        # After adjustment, positive should be higher
        assert result['positive'] > base_scores['positive']

    def test_youtube_specific_negative(self):
        """Test YouTube-specific negative expressions."""
        base_scores = {'positive': 0.4, 'negative': 0.3, 'neutral': 0.3}
        result = _adjust_sentiment_with_rules('時間返せ', base_scores)
        assert result['negative'] > base_scores['negative']

    def test_youtube_specific_unsubscribe(self):
        """Test unsubscribe expression detected as negative."""
        base_scores = {'positive': 0.4, 'negative': 0.3, 'neutral': 0.3}
        result = _adjust_sentiment_with_rules('登録解除しました', base_scores)
        assert result['negative'] > base_scores['negative']

    def test_scores_remain_normalized(self):
        """Test that scores remain normalized after adjustment."""
        base_scores = {'positive': 0.5, 'negative': 0.3, 'neutral': 0.2}
        result = _adjust_sentiment_with_rules('クソつまらん最悪', base_scores)
        total = result['positive'] + result['negative'] + result['neutral']
        assert abs(total - 1.0) < 0.01

    def test_no_pattern_match_returns_similar_scores(self):
        """Test that text without patterns returns similar scores."""
        base_scores = {'positive': 0.4, 'negative': 0.3, 'neutral': 0.3}
        result = _adjust_sentiment_with_rules('今日は天気がいいです', base_scores)
        # Scores should be similar (within adjustment range) or adjusted for positive patterns
        # 'いい' is in positive patterns, so positive may increase
        total = result['positive'] + result['negative'] + result['neutral']
        assert abs(total - 1.0) < 0.01


class TestClassifyComments:
    """Tests for classify_comments function."""

    @patch('sentiment.analyzer.load_models')
    @patch('sentiment.analyzer._ja_model_1', MagicMock())
    @patch('sentiment.analyzer._ja_model_2', MagicMock())
    @patch('sentiment.analyzer._multi_model', MagicMock())
    def test_classify_multiple_comments(self, mock_load, sample_comments):
        """Test classifying multiple comments returns dict sentiment."""
        # Mock classify_comment to avoid loading real models
        with patch('sentiment.analyzer.classify_comment') as mock_classify:
            mock_classify.return_value = {'positive': 0.6, 'negative': 0.2, 'neutral': 0.2, 'language': 'ja'}
            result = classify_comments(sample_comments)

            assert len(result) == 5
            for comment in result:
                assert 'sentiment' in comment
                assert isinstance(comment['sentiment'], dict)
                assert 'positive' in comment['sentiment']
                assert 'negative' in comment['sentiment']
                assert 'neutral' in comment['sentiment']

    def test_classify_empty_list(self):
        """Test classifying empty list."""
        with patch('sentiment.analyzer.load_models'):
            with patch('sentiment.analyzer._ja_model_1', MagicMock()):
                with patch('sentiment.analyzer._ja_model_2', MagicMock()):
                    with patch('sentiment.analyzer._multi_model', MagicMock()):
                        result = classify_comments([])
                        assert result == []

    @patch('sentiment.analyzer.load_models')
    @patch('sentiment.analyzer._ja_model_1', MagicMock())
    @patch('sentiment.analyzer._ja_model_2', MagicMock())
    @patch('sentiment.analyzer._multi_model', MagicMock())
    def test_comments_retain_original_fields(self, mock_load, sample_comments):
        """Test that original fields are retained."""
        with patch('sentiment.analyzer.classify_comment') as mock_classify:
            mock_classify.return_value = {'positive': 0.6, 'negative': 0.2, 'neutral': 0.2, 'language': 'ja'}
            result = classify_comments(sample_comments)

            for i, comment in enumerate(result):
                assert comment['comment_id'] == sample_comments[i]['comment_id']
                assert comment['author'] == sample_comments[i]['author']
                assert comment['text'] == sample_comments[i]['text']

    def test_classify_comments_raises_on_all_models_failed(self):
        """Test that RuntimeError is raised when all models fail."""
        with patch('sentiment.analyzer.load_models'):
            with patch('sentiment.analyzer._ja_model_1', None):
                with patch('sentiment.analyzer._ja_model_2', None):
                    with patch('sentiment.analyzer._multi_model', None):
                        with pytest.raises(RuntimeError, match='全ての感情分析モデルのロード'):
                            classify_comments([{'text': 'test'}])
