"""Tests for aggregation summarizer."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from aggregate.summarizer import aggregate_video


def _make_pos_comment():
    """Create a comment with positive sentiment scores."""
    return {'sentiment': {'positive': 0.9, 'negative': 0.05, 'neutral': 0.05}}


def _make_neg_comment():
    """Create a comment with negative sentiment scores."""
    return {'sentiment': {'positive': 0.05, 'negative': 0.9, 'neutral': 0.05}}


def _make_neutral_comment():
    """Create a comment with neutral sentiment scores."""
    return {'sentiment': {'positive': 0.2, 'negative': 0.2, 'neutral': 0.6}}


class TestAggregateVideo:
    """Tests for aggregate_video function."""

    def test_aggregate_all_positive(self):
        """Test aggregation with all positive comments."""
        video = {'video_id': 'abc123'}
        comments = [_make_pos_comment() for _ in range(10)]

        result = aggregate_video(video, comments)

        assert result['video_id'] == 'abc123'
        assert result['total_comments'] == 10
        assert result['positive_count'] == 10
        assert result['negative_count'] == 0
        assert result['other_count'] == 0
        assert result['positive_ratio'] == 1.0
        assert result['negative_ratio'] == 0.0

    def test_aggregate_all_negative(self):
        """Test aggregation with all negative comments."""
        video = {'video_id': 'abc123'}
        comments = [_make_neg_comment() for _ in range(10)]

        result = aggregate_video(video, comments)

        assert result['positive_count'] == 0
        assert result['negative_count'] == 10
        assert result['other_count'] == 0
        assert result['positive_ratio'] == 0.0
        assert result['negative_ratio'] == 1.0

    def test_aggregate_mixed(self):
        """Test aggregation with mixed sentiment."""
        video = {'video_id': 'abc123'}
        comments = [
            *[_make_pos_comment() for _ in range(5)],
            *[_make_neg_comment() for _ in range(3)],
            *[_make_neutral_comment() for _ in range(2)],
        ]

        result = aggregate_video(video, comments)

        assert result['total_comments'] == 10
        assert result['positive_count'] == 5
        assert result['negative_count'] == 3
        assert result['other_count'] == 2
        assert result['positive_ratio'] == 0.5
        assert result['negative_ratio'] == 0.3

    def test_aggregate_empty_comments(self):
        """Test aggregation with empty comments list."""
        video = {'video_id': 'abc123'}
        comments = []

        result = aggregate_video(video, comments)

        assert result['total_comments'] == 0
        assert result['positive_count'] == 0
        assert result['negative_count'] == 0
        assert result['other_count'] == 0
        assert result['positive_ratio'] == 0.0
        assert result['negative_ratio'] == 0.0

    def test_aggregate_single_comment(self):
        """Test aggregation with single comment."""
        video = {'video_id': 'abc123'}
        comments = [_make_pos_comment()]

        result = aggregate_video(video, comments)

        assert result['total_comments'] == 1
        assert result['positive_count'] == 1
        assert result['positive_ratio'] == 1.0

    def test_aggregate_has_analyzed_at(self):
        """Test that result includes analyzed_at timestamp."""
        video = {'video_id': 'abc123'}
        comments = []

        result = aggregate_video(video, comments)

        assert 'analyzed_at' in result
        assert result['analyzed_at'] is not None

    def test_aggregate_ratio_precision(self):
        """Test ratio precision (4 decimal places)."""
        video = {'video_id': 'abc123'}
        comments = [
            _make_pos_comment(),
            _make_neg_comment(),
            _make_neg_comment(),
        ]

        result = aggregate_video(video, comments)

        # 1/3 = 0.3333
        assert result['positive_ratio'] == 0.3333
        # 2/3 = 0.6667
        assert result['negative_ratio'] == 0.6667

    def test_aggregate_with_sample_classified_comments(self, sample_classified_comments):
        """Test aggregation using sample_classified_comments fixture."""
        video = {'video_id': 'test_video'}

        result = aggregate_video(video, sample_classified_comments)

        # 5 comments: c1(pos), c2(neg), c3(neutral), c4(pos), c5(neg)
        assert result['total_comments'] == 5
        assert result['positive_count'] == 2  # c1, c4
        assert result['negative_count'] == 2  # c2, c5
        assert result['other_count'] == 1     # c3

    def test_aggregate_returns_average_scores(self):
        """Test that aggregation returns average sentiment scores."""
        video = {'video_id': 'abc123'}
        comments = [
            {'sentiment': {'positive': 0.8, 'negative': 0.1, 'neutral': 0.1}},
            {'sentiment': {'positive': 0.6, 'negative': 0.3, 'neutral': 0.1}},
        ]

        result = aggregate_video(video, comments)

        # Average: (0.8 + 0.6) / 2 = 0.7
        assert result['positive_score'] == 0.7
        # Average: (0.1 + 0.3) / 2 = 0.2
        assert result['negative_score'] == 0.2
        # Average: (0.1 + 0.1) / 2 = 0.1
        assert result['neutral_score'] == 0.1
