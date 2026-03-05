import pytest
from unittest.mock import patch
from app.utils import send_emailTls2
from email.message import Message

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

        # Assert: server.send_message was called
        assert instance.send_message.called

        # Get the message sent
        call_args = instance.send_message.call_args
        msg_obj = call_args[0][0]

        # Verify it's a message object
        assert isinstance(msg_obj, Message)

        # Verify contents
        msg_str = msg_obj.as_string()
        # Header should encode the subject
        assert "=?utf-8?b?UHJpY2UgaW4g4oKs?=" in msg_str

        # The body should contain the Euro symbol, either literally (if 8bit) or encoded
        assert "€" in msg_str or "4oKs" in msg_str or "=E2=82=AC" in msg_str
