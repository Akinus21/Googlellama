# resources.py

# Scopes
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://mail.google.com/",
]
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]
CONTACTS_SCOPES = ["https://www.googleapis.com/auth/contacts"]
TASKS_SCOPES = ["https://www.googleapis.com/auth/tasks"]
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]

ALL_SCOPES = GMAIL_SCOPES + CALENDAR_SCOPES + CONTACTS_SCOPES + TASKS_SCOPES + DRIVE_SCOPES