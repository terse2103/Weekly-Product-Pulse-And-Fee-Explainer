import pytest
from phase2_cleaning.pii_filter import redact_pii, filter_pii
from phase2_cleaning.pii_validator import validate_no_pii

def test_email_redaction():
    text = "Please contact me at admin-test.123@example-mail.co.in or not."
    redacted = redact_pii(text)
    assert "[EMAIL]" in redacted
    assert "admin-test.123@example-mail.co.in" not in redacted

def test_phone_redaction():
    texts = [
        "Call me on +91-9876543210 please.",
        "My number is 9876543210.",
        "+91 9876543210 is my whatsapp."
    ]
    for text in texts:
        redacted = redact_pii(text)
        assert "[PHONE]" in redacted
        assert "9876543210" not in redacted

def test_upi_redaction():
    text = "Transferred to my upi ID john.doe@okhdfcbank yesterday."
    redacted = redact_pii(text)
    assert "[REDACTED]" in redacted
    assert "john.doe@okhdfcbank" not in redacted

def test_bank_account_redaction():
    text = "My account number is 1234567890123."
    redacted = redact_pii(text)
    assert "[REDACTED]" in redacted
    assert "1234567890123" not in redacted

def test_username_mentions_redaction():
    text = "Hey @indmoney_support can you fix this?"
    redacted = redact_pii(text)
    assert "[USER]" in redacted
    assert "@indmoney_support" not in redacted

def test_integration_and_validator():
    """ Tests that filter properly removes PII and validator returns safe. """
    mock_reviews = [
        {"review_id": "r1", "text": "App is good @author but email me at x@y.com"},
        {"review_id": "r2", "text": "Call +91-9999999999 for my UPI id bob@upi"},
        {"review_id": "r3", "text": "Normally text with no PII whatsoever."}
    ]
    
    # Run Filter
    clean_reviews = filter_pii(mock_reviews)
    
    # Assert Filter logic
    assert "[USER]" in clean_reviews[0]['text']
    assert "[EMAIL]" in clean_reviews[0]['text']
    assert "[PHONE]" in clean_reviews[1]['text']
    assert "[REDACTED]" in clean_reviews[1]['text']
    assert "x@y.com" not in clean_reviews[0]['text']
    
    # Run Validator
    assert validate_no_pii(clean_reviews) is True

def test_validator_fails_on_leak():
    """ Tests if validator catches a fake leak. """
    leaked_reviews = [{"review_id": "L1", "text": "Oops I left sample@email.com here."}]
    assert validate_no_pii(leaked_reviews) is False
