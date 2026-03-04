import pytest
from unittest.mock import patch
from app.utils import send_emailTls2

def test_email_encoding_with_euro_symbol():
    # Character \u20ac is the Euro symbol €
    sender = "sender@example.com"
    password = "password"
    server = "smtp.example.com"
    port = 587
    recipient = "recipient@example.com"
    subject = "Price in €"
    body = "<html><body>The total is 100€.</body></html>"

    with patch('smtplib.SMTP') as mock_smtp:
        # Mock the server instance
        instance = mock_smtp.return_value

        # Act
        send_emailTls2(sender, password, server, port, recipient, subject, body)

        # Assert: server.sendmail was called
        assert instance.sendmail.called

        # Get the message sent
        call_args = instance.sendmail.call_args
        msg_str = call_args[0][2]

        # Verify that the Euro symbol is handled correctly in the raw message string
        # MIMEText with utf-8 should encode it
        assert "€" in msg_str or "=E2=82=AC" in msg_str or "4oKs" in msg_str # Check for literal or various encodings
