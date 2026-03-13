import os
import json
import pytest
from unittest.mock import patch, mock_open
from phase4_grouping.theme_classifier import classify_reviews
from phase4_grouping.validator import validate_distribution

@patch("phase4_grouping.theme_classifier.call_groq_json_mode")
@patch("os.path.exists")
def test_classify_reviews(mock_exists, mock_call_groq):
    mock_exists.return_value = True
    
    clean_reviews_data = json.dumps([{"review_id": "r1", "text": "app is good"}])
    themes_data = json.dumps([{"theme": "Good UI", "description": "Good UI"}])
    
    def side_effect(path, *args, **kwargs):
        if "clean_reviews.json" in path:
            return mock_open(read_data=clean_reviews_data).return_value
        elif "themes.json" in path:
            return mock_open(read_data=themes_data).return_value
        else:
            return mock_open(read_data="[]").return_value

    with patch("builtins.open", side_effect=side_effect) as m_open:
        mock_call_groq.return_value = {
            "classifications": [
                {"review_id": "r1", "theme": "Good UI"}
            ]
        }
        
        classify_reviews()
        mock_call_groq.assert_called_once()
        
        # Ensure themed_reviews.json is opened for writing
        write_calls = [c for c in m_open.mock_calls if 'themed_reviews.json' in c.args[0] and c.args[1] == 'w']
        assert len(write_calls) > 0

def test_validate_distribution_valid():
    with patch("os.path.exists", return_value=True):
        valid_data = json.dumps([
            {"review_id": "1", "theme": "Theme A"},
            {"review_id": "2", "theme": "Theme B"},
            {"review_id": "3", "theme": "Theme A"}
        ])
        with patch("builtins.open", mock_open(read_data=valid_data)):
            # None exceed 60% if total is 3 maybe? Wait, 2/3 is 66% so it will fail.
            pass

    with patch("os.path.exists", return_value=True):
        valid_data = json.dumps([
            {"review_id": "1", "theme": "Theme A"},
            {"review_id": "2", "theme": "Theme B"}
        ])
        with patch("builtins.open", mock_open(read_data=valid_data)):
            assert validate_distribution() is True

def test_validate_distribution_invalid():
    with patch("os.path.exists", return_value=True):
        invalid_data = json.dumps([
            {"review_id": "1", "theme": "Theme A"},
            {"review_id": "2", "theme": "Theme A"},
            {"review_id": "3", "theme": "Theme A"}
        ])
        with patch("builtins.open", mock_open(read_data=invalid_data)):
            assert validate_distribution() is False
