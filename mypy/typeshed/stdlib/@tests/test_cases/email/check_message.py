from email.headerregistry import Address
from email.message import EmailMessage

msg = EmailMessage()
msg["To"] = "receiver@example.com"
msg["From"] = Address("Sender Name", "sender", "example.com")
