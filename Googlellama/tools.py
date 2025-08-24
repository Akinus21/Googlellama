# tools/google_tools.py

import os
import json
import dotenv
import asyncio
from pathlib import Path
import traceback
from typing import Optional, List
from akinus.web.server.mcp import mcp
from akinus.utils.logger import log
from akinus.web.utils.retry import retry_async
from akinus.web.google.auth import get_credentials

from googleapiclient.discovery import build
import io
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

import asyncio
from pyppeteer import launch
from pyppeteer_stealth import stealth
from fastapi import HTTPException
from pathlib import Path
from email.utils import parseaddr

import warnings
warnings.filterwarnings("ignore", message="file_cache is only supported with oauth2client")

import logging
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

from akinus.utils.app_details import PROJECT_ROOT, PYPROJECT_PATH, app_name

ALL_SCOPES = dotenv.dotenv_values(PROJECT_ROOT / ".env").get("ALL_SCOPES", "").split(",")
GMAIL_SCOPES = dotenv.dotenv_values(PROJECT_ROOT / ".env").get("GMAIL_SCOPES", "").split(",")
CALENDAR_SCOPES = dotenv.dotenv_values(PROJECT_ROOT / ".env").get("CALENDAR_SCOPES", "").split(",")
CONTACTS_SCOPES = dotenv.dotenv_values(PROJECT_ROOT / ".env").get("CONTACTS_SCOPES", "").split(",")
TASKS_SCOPES = dotenv.dotenv_values(PROJECT_ROOT / ".env").get("TASKS_SCOPES", "").split(",")
DRIVE_SCOPES = dotenv.dotenv_values(PROJECT_ROOT / ".env").get("DRIVE_SCOPES", "").split(",")
# Ensure all scopes are defined

# Token storage
TOKEN_PATH = PROJECT_ROOT / "data" / "token.json"

# --- Support functions ---
def sync_log(*args, **kwargs):
    try:
        asyncio.get_event_loop().create_task(log(*args, **kwargs))
    except RuntimeError:
        # If no loop is running (or running in a thread), fallback:
        asyncio.run(log(*args, **kwargs))


def get_gmail_service():
    creds = get_credentials(GMAIL_SCOPES)
    return build("gmail", "v1", credentials=creds)

def get_drive_service():
    creds = get_credentials(DRIVE_SCOPES)
    return build("drive", "v3", credentials=creds)

async def get_drive_file_id(service, filename):
    query = f"name='{filename}' AND trashed=false"

    results = service.files().list(
        q=query,
        spaces="drive",
        fields="files(id, name, mimeType, modifiedTime, size)",
        orderBy="modifiedTime desc"
    ).execute()

    files = results.get("files", [])

    if not files:
        # No file found, create a blank one
        print(f"No file found for {filename}. Creating new blank file.")
        file_metadata = {"name": filename}
        file = service.files().create(body=file_metadata, fields="id").execute()
        return file["id"]

    # Sort files by size (largest first), then by modifiedTime
    files = sorted(files, key=lambda f: int(f.get("size", 0)), reverse=True)

    # Pick the first non-empty file if available
    for f in files:
        size = int(f.get("size", 0))
        if size > 0:
            return f["id"]

    # If all files are empty, fallback to the newest one
    newest_file = files[0]
    return newest_file["id"]

async def read_drive_file(service, file_id):
    file_info = service.files().get(fileId=file_id, fields="id, name, mimeType").execute()

    if file_info["mimeType"] == "application/vnd.google-apps.document":
        request = service.files().export_media(fileId=file_id, mimeType="text/plain")
    else:
        request = service.files().get_media(fileId=file_id)

    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    fh.seek(0)
    content = fh.read().decode("utf-8").strip()

    if not content:
        return []  # Empty file

    return [line.strip() for line in content.splitlines() if line.strip()]


async def write_drive_file(service, file_id, lines):
    content = "\n".join(lines)
    fh = io.BytesIO(content.encode("utf-8"))
    media = MediaIoBaseUpload(fh, mimetype="text/plain", resumable=True)
    service.files().update(fileId=file_id, media_body=media).execute()

# ---- Filter functions using Drive ----

async def get_filter_string(filename="delete_filter.txt"):
    service = get_drive_service()
    file_id = await get_drive_file_id(service, filename)
    lines = await read_drive_file(service, file_id)

    # Ensure it always returns a list (even if empty)
    return lines or []

async def add_to_filter_string(text: str, filename="delete_filter.txt"):
    _, email = parseaddr(text)
    if not email:
        return
    email = email.lower().strip()

    service = get_drive_service()
    file_id = await get_drive_file_id(service, filename)
    lines = await read_drive_file(service, file_id)

    if email in lines:
        await log("INFO", "google_tools", f"Sender {email} already in filter list ({filename}).")
        return

    lines.append(email)
    await write_drive_file(service, file_id, lines)
    await log("INFO", "google_tools", f"Added to filter ({filename}): {email}")

async def remove_from_filter_string(text: str, filename="delete_filter.txt"):
    service = get_drive_service()
    file_id = await get_drive_file_id(service, filename)
    lines = await read_drive_file(service, file_id)
    if text not in lines:
        return
    lines = [line for line in lines if line != text]
    await write_drive_file(service, file_id, lines)
    await log("INFO", "google_tools", f"Removed from filter ({filename}): {text}")

# Convenience wrappers for delete and archive filters:

async def add_to_delete_filter_string(text: str):
    await add_to_filter_string(text, filename="delete_filter.txt")

async def remove_from_delete_filter_string(text: str):
    await remove_from_filter_string(text, filename="delete_filter.txt")

async def add_to_archive_filter_string(text: str):
    await add_to_filter_string(text, filename="archive_filter.txt")

async def remove_from_archive_filter_string(text: str):
    await remove_from_filter_string(text, filename="archive_filter.txt")


async def add_if_labeled_delete():
    """
    Scans Gmail for messages labeled 'Delete' and adds their senders to delete_filter.txt.
    Handles pagination to process all matching messages.
    Ignores messages in Trash or Spam.
    """

    from googleapiclient.discovery import build

    creds = get_credentials(GMAIL_SCOPES)
    svc = build("gmail", "v1", credentials=creds)

    # Find the "Delete" label ID
    labels_response = svc.users().labels().list(userId="me").execute()
    delete_label_id = None
    for label in labels_response.get("labels", []):
        if label["name"].lower() == "delete":
            delete_label_id = label["id"]
            break

    if not delete_label_id:
        log("ERROR", "google_tools", "Delete label not found in Gmail account.")
        return {"status": "error", "message": "Delete label not found."}

    count = 0
    next_page_token = None

    while True:
        # List messages with the Delete label, paginated
        resp = svc.users().messages().list(
            userId="me",
            labelIds=[delete_label_id],
            maxResults=500,
            pageToken=next_page_token
        ).execute()

        items = resp.get("messages", [])
        if not items:
            break

        for m in items:
            try:
                meta = svc.users().messages().get(userId="me", id=m["id"], format="metadata").execute()
                labels = meta.get("labelIds", [])
                # Ignore messages in TRASH or SPAM
                if "TRASH" in labels or "SPAM" in labels:
                    continue

                headers = meta.get("payload", {}).get("headers", [])
                sender = next((h["value"] for h in headers if h["name"].lower() == "from"), None)
                if sender:
                    _, email = parseaddr(sender)
                    if email:
                        email = email.lower().strip()
                        await add_to_delete_filter_string(email)
                        await log("INFO", "google_tools", f"Added sender {email} to filter list for message {m['id']}")
                        count += 1
            except Exception as e:
                log("ERROR", "google_tools", f"Error processing message {m['id']}: {e}")
                continue

        next_page_token = resp.get("nextPageToken")
        if not next_page_token:
            break

    return {"status": "added to filter list", "count": count}


async def add_if_labeled_archive():
    """
    Scans Gmail for messages labeled 'Archive' and adds their senders to filter.txt.
    Handles pagination to process all matching messages.
    Ignores messages in TRASH or SPAM.
    """
    from googleapiclient.discovery import build

    creds = get_credentials(GMAIL_SCOPES)
    svc = build("gmail", "v1", credentials=creds)

    archive_label_id = get_label_id_by_name(svc, "me", "Save")
    if not archive_label_id:
        log("ERROR", "google_tools", "Archive label not found in Gmail account.")
        return {"status": "error", "message": "Archive label not found."}

    count = 0
    next_page_token = None

    while True:
        resp = svc.users().messages().list(
            userId="me",
            labelIds=[archive_label_id],
            maxResults=500,
            pageToken=next_page_token
        ).execute()

        items = resp.get("messages", [])
        if not items:
            break

        for m in items:
            try:
                meta = svc.users().messages().get(userId="me", id=m["id"], format="metadata").execute()
                labels = meta.get("labelIds", [])
                if "TRASH" in labels or "SPAM" in labels:
                    continue

                headers = meta.get("payload", {}).get("headers", [])
                sender = next((h["value"] for h in headers if h["name"].lower() == "from"), None)
                if sender:
                    _, email = parseaddr(sender)
                    if email:
                        email = email.lower().strip()
                        await add_to_delete_filter_string(email)
                        await log("INFO", "google_tools", f"Added sender {email} to filter list for message {m['id']}")
                        count += 1
            except Exception as e:
                log("ERROR", "google_tools", f"Error processing archive-labeled message {m['id']}: {e}")
                continue

        next_page_token = resp.get("nextPageToken")
        if not next_page_token:
            break

    return {"status": "added to filter list", "label": "Archive", "count": count}


def get_label_id_by_name(svc, user_id: str, label_name: str) -> str | None:
    """
    Retrieves the label ID for a given label name.
    Returns None if not found.
    """
    try:
        labels_resp = svc.users().labels().list(userId=user_id).execute()
        labels = labels_resp.get("labels", [])
        for label in labels:
            if label.get("name", "").lower() == label_name.lower():
                return label.get("id")
    except Exception as e:
        log("ERROR", "google_tools", f"Error retrieving labels: {e}")
    return None

async def clean_filter_file(path):
    """Reads a filter file, normalizes it to unique email-only lines, and rewrites it."""
    if not path.exists():
        return False

    with open(path, "r") as f:
        raw_lines = [line.strip() for line in f.readlines() if line.strip()]

    cleaned_emails = set()
    for line in raw_lines:
        name, email = parseaddr(line)
        if email and "@" in email:  # ensure it's valid
            cleaned_emails.add(email.lower().strip())

    # Rewrite file with deduplicated emails
    with open(path, "w") as f:
        for email in sorted(cleaned_emails):
            f.write(email + "\n")

    return True

async def process_sender_group(senders: List[str], action: str):
    """Processes a group of senders in parallel using batch operations."""
    tasks = [process_sender(sender, action) for sender in senders]
    results = await asyncio.gather(*tasks)
    return sum(results)


async def process_sender(sender: str, action: str):
    """Fetches messages for a sender and performs batch delete or archive."""
    await log("INFO", "google_tools", f"Processing sender ({action}): {sender}")

    try:
        messages = await retry_async(
            gmail_list,
            f"in:inbox from:{sender}",
            retries=1,
            logger=lambda m: sync_log("WARNING", "google_tools", m)
        )
    except Exception as e:
        await log("ERROR", "google_tools", f"Failed fetching messages for {sender}: {e}. Skipping.")
        return 0

    if not messages:
        return 0

    message_ids = [m["id"] for m in messages]

    try:
        if action == "delete":
            await gmail_batch_delete(message_ids)
        elif action == "archive":
            await gmail_batch_archive(message_ids)
        else:
            raise ValueError(f"Unknown action: {action}")
    except Exception as e:
        await log("ERROR", "google_tools", f"Batch {action} failed for {sender}: {e}")
        return 0

    await log("INFO", "google_tools", f"|__ {action.capitalize()}d {len(message_ids)} emails from {sender}")
    return len(message_ids)


async def gmail_batch_delete(message_ids: List[str]):
    """Deletes multiple messages in one API call."""
    service = get_gmail_service()
    service.users().messages().batchDelete(userId="me", body={"ids": message_ids}).execute()


async def gmail_batch_archive(message_ids: List[str]):
    """Archives multiple messages in one API call (removes 'INBOX' label)."""
    service = get_gmail_service()
    service.users().messages().batchModify(
        userId="me",
        body={"ids": message_ids, "removeLabelIds": ["INBOX"]}
    ).execute()

# --- Gmail operations ---
from asyncio import get_running_loop

BATCH_SIZE = 100  # Max email addresses per query batch

@mcp.tool()
async def clean_up_inbox():
    """
    Cleans up the inbox by:
    - Cleaning and deduplicating delete_filter.txt and archive_filter.txt
    - Adding senders of emails labeled 'Delete' to delete_filter.txt
    - Deleting all emails matching delete_filter.txt in batched queries
    - Archiving all emails matching archive_filter.txt in batched queries
    - Archiving all read emails in the inbox
    """

    await add_if_labeled_delete()

    delete_senders = await get_filter_string("delete_filter.txt")
    archive_senders = await get_filter_string("archive_filter.txt")

    if not delete_senders:
        await log("WARNING", "google_tools", "Delete filter file is empty.")
        return {"error": "Delete filter file is empty."}

    if not archive_senders:
        await log("WARNING", "google_tools", "Archive filter file is empty.")
        return {"error": "Archive filter file is empty."}

    # --- DELETE in batched queries ---
    deleted_total = await process_batched(delete_senders, action="delete")

    # --- ARCHIVE in batched queries ---
    archived_total = await process_batched(archive_senders, action="archive")

    # --- Archive all read emails in Inbox ---
    await log("INFO", "google_tools", "Archiving all read emails in Inbox...")
    try:
        result = await retry_async(
            gmail_modify,
            query="is:read in:inbox",
            add_labels=["archive"],
            retries=1,
            logger=lambda m: sync_log("WARNING", "google_tools", m)
        )
    except Exception as e:
        await log("ERROR", "google_tools", f"Failed archiving read emails: {e}")
        result = {"count": 0}

    read_archived_count = result.get("count", 0)
    archived_total += read_archived_count

    sender_numbers = len(delete_senders) + len(archive_senders)

    await log(
        "INFO",
        "google_tools",
        f"Cleaned inbox: {deleted_total} deleted, {archived_total} archived from {sender_numbers} senders (including {read_archived_count} read emails)."
    )

    return {
        "status": "cleanup complete",
        "senders_processed": sender_numbers,
        "deleted_total": deleted_total,
        "archived_total": archived_total,
        "archived_read_emails": read_archived_count,
    }


async def process_batched(senders: List[str], action: str):
    """Splits senders into batches of BATCH_SIZE and processes each batch."""
    total = 0
    for i in range(0, len(senders), BATCH_SIZE):
        batch = senders[i:i + BATCH_SIZE]
        query = " OR ".join([f"from:{s}" for s in batch])
        total += await process_bulk(query, action)
    return total


async def process_bulk(query: str, action: str):
    """Fetches all matching messages for a query and performs batch delete or archive."""
    await log("INFO", "google_tools", f"Processing bulk {action} query: {query[:200]}{'...' if len(query)>200 else ''}")

    try:
        messages = await retry_async(
            gmail_list,
            f"in:inbox ({query})",
            retries=1,
            logger=lambda m: sync_log("WARNING", "google_tools", m)
        )
    except Exception as e:
        await log("ERROR", "google_tools", f"Failed fetching messages for bulk {action}: {e}")
        return 0

    if not messages:
        return 0

    message_ids = [m["id"] for m in messages]

    try:
        if action == "delete":
            await gmail_batch_delete(message_ids)
        elif action == "archive":
            await gmail_batch_archive(message_ids)
        else:
            raise ValueError(f"Unknown action: {action}")
    except Exception as e:
        await log("ERROR", "google_tools", f"Batch {action} failed: {e}")
        return 0

    await log("INFO", "google_tools", f"|__ {action.capitalize()}d {len(message_ids)} messages in this batch.")
    return len(message_ids)


async def gmail_batch_delete(message_ids: List[str]):
    """Deletes multiple messages in one API call."""
    service = get_gmail_service()
    service.users().messages().batchDelete(userId="me", body={"ids": message_ids}).execute()


async def gmail_batch_archive(message_ids: List[str]):
    """Archives multiple messages in one API call (removes 'INBOX' label)."""
    service = get_gmail_service()
    service.users().messages().batchModify(
        userId="me",
        body={"ids": message_ids, "removeLabelIds": ["INBOX"]}
    ).execute()

@mcp.tool()
async def clean_up_archive():
    """
    Cleans up the archive by:
    - Cleaning and deduplicating delete_filter.txt
    - Adding senders of emails labeled 'Delete' to delete_filter.txt
    - Deleting archived emails from delete_filter.txt in batches
    - Deleting archived emails older than 6 months that are NOT marked Important
    """

    await add_if_labeled_delete()

    delete_senders = await get_filter_string("delete_filter.txt")

    if not delete_senders:
        await log("WARNING", "google_tools", "Delete filter file is empty.")
        return {"error": "Delete filter file is empty."}

    # --- DELETE archived emails matching delete_filter.txt ---
    deleted_total = await process_batched_archive(delete_senders)

    # --- DELETE archived emails older than 6 months and NOT Important ---
    await log("INFO", "google_tools", "Removing archived emails older than 6 months and NOT marked Important...")
    try:
        old_messages = await retry_async(
            gmail_list,
            "-in:inbox older_than:6m -label:IMPORTANT",
            retries=1,
            logger=lambda m: sync_log("WARNING", "google_tools", m)
        )

        if old_messages:
            message_ids = [m["id"] for m in old_messages]
            await gmail_batch_delete(message_ids)
            await log("INFO", "google_tools", f"|__ Deleted {len(message_ids)} old archived emails (older than 6 months, not Important)")
            deleted_total += len(message_ids)
        else:
            await log("INFO", "google_tools", "No old archived emails found.")

    except Exception as e:
        await log("ERROR", "google_tools", f"Failed removing old archived emails: {e}")

    await log(
        "INFO",
        "google_tools",
        f"Cleaned archive: {deleted_total} deleted from {len(delete_senders)} senders (including old unimportant emails)."
    )

    return {
        "status": "archive cleanup complete",
        "senders_processed": len(delete_senders),
        "deleted_total": deleted_total,
    }


async def process_batched_archive(senders: List[str]):
    """Splits senders into batches of BATCH_SIZE and deletes their archived messages."""
    total_deleted = 0
    for i in range(0, len(senders), BATCH_SIZE):
        batch = senders[i:i + BATCH_SIZE]
        query = " OR ".join([f"from:{s}" for s in batch])
        total_deleted += await process_bulk_archive(query)
    return total_deleted


async def process_bulk_archive(query: str):
    """Fetches archived messages for a query and deletes them in bulk."""
    await log("INFO", "google_tools", f"Processing archived delete batch: {query[:200]}{'...' if len(query)>200 else ''}")

    try:
        messages = await retry_async(
            gmail_list,
            f"-in:inbox ({query})",  # Archived only (not in inbox)
            retries=1,
            logger=lambda m: sync_log("WARNING", "google_tools", m)
        )
    except Exception as e:
        await log("ERROR", "google_tools", f"Failed fetching archived messages for batch: {e}")
        return 0

    if not messages:
        return 0

    message_ids = [m["id"] for m in messages]

    try:
        await gmail_batch_delete(message_ids)
        await log("INFO", "google_tools", f"|__ Deleted {len(message_ids)} archived messages in this batch.")
        return len(message_ids)
    except Exception as e:
        await log("ERROR", "google_tools", f"Batch delete failed: {e}")
        return 0

@mcp.tool()
async def add_sender_to_delete_list(sender: str):
    """
    Adds a sender's email address to the delete list.
    The filter is stored in a text file.
    Returns a confirmation message.
    """
    if not sender or "@" not in sender:
        await log("WARNING", "google_tools", f"Invalid sender email: {sender}")
        return {"error": "Invalid sender email provided."}

    add_to_delete_filter_string(sender)
    await log("INFO", "google_tools", f"Added sender {sender} to delete filter list")
    return {"status": "added", "sender": sender}

@mcp.tool()
async def add_sender_to_archive_list(sender: str):
    """
    Adds a sender's email address to the delete list.
    The filter is stored in a text file.
    Returns a confirmation message.
    """
    if not sender or "@" not in sender:
        await log("WARNING", "google_tools", f"Invalid sender email: {sender}")
        return {"error": "Invalid sender email provided."}

    add_to_archive_filter_string(sender)
    await log("INFO", "google_tools", f"Added sender {sender} to delete filter list")
    return {"status": "added", "sender": sender}

@mcp.tool()
async def gmail_list(query: str = None, max_results: int = 1000, sub: bool = False):
    """
    Lists Gmail messages matching the query, returning metadata like Subject, From, and Date.
    Returns a list of dictionaries with message ID, subject, sender, and date.
    If sub is True, it logs the action with a subordinate indentation.
    """
    creds = get_credentials(GMAIL_SCOPES)
    svc = build("gmail", "v1", credentials=creds)
    resp = svc.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    items = resp.get("messages", [])
    results = []
    for m in items:
        meta = svc.users().messages().get(userId="me", id=m["id"], format="metadata",
                                          metadataHeaders=["Subject","From","Date"]).execute()
        hdrs = {h["name"]: h["value"] for h in meta["payload"]["headers"]}
        results.append({"id": m["id"], **hdrs})
    
    if sub:
        await log("INFO", "google_tools", f"|__ Listed {len(results)} Gmail messages")
    else: 
        await log("INFO", "google_tools", f"Listed {len(results)} Gmail messages")

    return results

@mcp.tool()
async def delete_multiple_emails(query: str = None, max_results: int = 1000):
    """
    Deletes multiple Gmail messages matching the query.
    Returns the count of deleted messages.
    """
    creds = get_credentials(GMAIL_SCOPES)
    svc = build("gmail", "v1", credentials=creds)
    resp = svc.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    items = resp.get("messages", [])
    results = []
    for m in items:
        results.append(m["id"])
    
    total = len(results)


    await log("INFO", "google_tools", f"Deleting {total} Gmail messages matching query '{query}'")

    for d in results:
        try:
            svc.users().messages().delete(userId="me", id=d).execute()
        except Exception as e:
            await log("ERROR", "google_tools", f"Error deleting message {d}: {e}")
    await log("INFO", "google_tools", f"Deleted {total} Gmail messages matching query '{query}'")
    return {"status": "deleted", "count": total}

@mcp.tool()
async def gmail_send(to: str, subject: str, body: str):
    """
    Sends an email using the Gmail API.
    `to` is the recipient email address, `subject` is the email subject, and `body` is the email content.
    Returns the sent message ID.
    """
    import base64
    from email.mime.text import MIMEText
    creds = get_credentials(GMAIL_SCOPES)
    svc = build("gmail", "v1", credentials=creds)
    msg = MIMEText(body)
    msg["to"], msg["subject"] = to, subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    sent = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    await log("INFO", "google_tools", f"Sent Gmail message ID {sent['id']}")
    return sent

@mcp.tool()
async def gmail_modify(query: str = None, max_results: int = 1000, add_labels: list = None, remove_labels: list = None, sub: bool = False):
    """ Modifies Gmail messages matching the query by adding or removing labels.
    `add_labels` and `remove_labels` should be lists of label IDs or names.
    """
    
    creds = get_credentials(GMAIL_SCOPES)
    svc = build("gmail", "v1", credentials=creds)
    resp = svc.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    items = resp.get("messages", [])

    total = len(items)

    if sub:
        await log("INFO", "google_tools", f"|__ Modifying {total} Gmail messages matching query '{query}'")
    else:
        await log("INFO", "google_tools", f"Modifying {total} Gmail messages matching query '{query}'")

    # Normalize input
    add_labels = add_labels or []
    remove_labels = remove_labels or []

    # Translate high-level labels to actual Gmail label actions
    if "READ" in add_labels:
        add_labels.remove("READ")
        if "UNREAD" not in remove_labels:
            remove_labels.append("UNREAD")

    if "read" in add_labels:
        add_labels.remove("read")
        if "UNREAD" not in remove_labels:
            remove_labels.append("UNREAD")

    if "archive" in add_labels:
        add_labels.remove("archive")
        if "INBOX" not in remove_labels:
            remove_labels.append("INBOX")

    for item in items:
        msg_id = item.get("id")
        if not msg_id:
            
            if sub:
                await log("WARNING", "google_tools", f"|__ Skipping message with no ID: {item}")
            else:
                await log("WARNING", "google_tools", f"Skipping message with no ID: {item}")
            
            continue

        try:
            svc.users().messages().modify(
                userId="me",
                id=msg_id,
                body={
                    "addLabelIds": add_labels,
                    "removeLabelIds": remove_labels
                }
            ).execute()
        except Exception as e:
            await log("ERROR", "google_tools", f"Error modifying message {msg_id}: {e}")
            continue

    if sub:
        await log("INFO", "google_tools", f"|__ Modified {total} Gmail messages matching query '{query}'")
    else:     
        await log("INFO", "google_tools", f"Modified {total} Gmail messages matching query '{query}'")
    
    return {"status": "modified", "count": total, "query": query}

@mcp.tool()
async def gmail_delete(msg_id: str, type: str = "multiple", sub:bool = False):
    """ Deletes a Gmail message by its ID.
    `msg_id` should be the full message ID string.
    Returns a confirmation message.
    If type is single it logs the action for the single message,
    otherwise it does not log the single action, allowing bulk operations without excessive logging.
    """
    
    if not msg_id or not isinstance(msg_id, str) or msg_id.strip() == "":
        await log("WARNING", "google_tools", f"Invalid or empty msg_id passed to gmail_delete: '{msg_id}'")
        return {"error": "Invalid or empty msg_id provided."}

    try:
        creds = get_credentials(GMAIL_SCOPES)
        svc = build("gmail", "v1", credentials=creds)
        svc.users().messages().delete(userId="me", id=msg_id).execute()
        
        if type == "single":
            if sub:
                await log("INFO", "google_tools", f"|__ Deleted Gmail message {msg_id}")
            else:
                await log("INFO", "google_tools", f"Deleted Gmail message {msg_id}")
        
        return {"status": "deleted", "id": msg_id}

    except Exception as e:
        await log("ERROR", "google_tools", f"Error deleting Gmail message {msg_id}: {e}")
        return {"error": f"Failed to delete message {msg_id}: {str(e)}"}
    
@mcp.tool()
async def gmail_archive(msg_id: str, type: str = "multiple", sub:bool = False):
    """Archives a Gmail message by removing the 'Inbox' label.
    `msg_id` should be the full message ID string.
    Returns a confirmation message.
    if type is single it logs the action for the single message,
    otherwise it does not log the single action, allowing bulk operations without excessive logging.
    """

    if not msg_id or not isinstance(msg_id, str) or msg_id.strip() == "":
        await log("WARNING", "google_tools", f"Invalid or empty msg_id passed to gmail_archive: '{msg_id}'")
        return {"error": "Invalid or empty msg_id provided."}

    try:
        creds = get_credentials(GMAIL_SCOPES)
        svc = build("gmail", "v1", credentials=creds)
        
        # ✅ FIXED: Pass user_id explicitly
        inbox_label_id = get_label_id_by_name(svc, "me", "INBOX")

        if not inbox_label_id:
            raise Exception("Could not find INBOX label ID.")

        svc.users().messages().modify(
            userId="me",
            id=msg_id,
            body={
                "removeLabelIds": [inbox_label_id]
            }
        ).execute()

        if type == "single":
            if sub:
                await log("INFO", "google_tools", f"|__ Archived Gmail message {msg_id} by removing INBOX label.")
            else:
                await log("INFO", "google_tools", f"Archived Gmail message {msg_id} by removing INBOX label.")

        return {"status": "archived", "id": msg_id}

    except Exception as e:
        await log("ERROR", "google_tools", f"Error archiving Gmail message {msg_id}: {e}")
        return {"error": f"Failed to archive message {msg_id}: {str(e)}"}


# --- Calendar operations ---
@mcp.tool()
async def calendar_list(start: str = None, end: str = None, max_results: int = 10):
    """ Lists upcoming calendar events within the specified time range.
    `start` and `end` should be RFC3339 timestamps (e.g., 2023-10-01T00:00:00Z).
    `max_results` limits the number of events returned.
    Returns a list of event dictionaries with details like summary, start time, and end time.
    """

    creds = get_credentials(CALENDAR_SCOPES)
    svc = build("calendar", "v3", credentials=creds)
    params = {"calendarId": "primary", "maxResults": max_results, "singleEvents": True, "orderBy": "startTime"}
    if start: params["timeMin"] = start
    if end: params["timeMax"] = end
    evs = svc.events().list(**params).execute().get("items", [])
    await log("INFO", "google_tools", f"Fetched {len(evs)} events")
    return evs

@mcp.tool()
async def calendar_add(summary: str, start: str, end: str, description: str = None, location: str = None):
    """
    Creates a new calendar event with the specified details.
    `summary` is the event title, `start` and `end` are RFC3339 timestamps (e.g., 2023-10-01T00:00:00Z).
    `description` and `location` are optional.
    Returns the created event details.
    """

    creds = get_credentials(CALENDAR_SCOPES)
    svc = build("calendar", "v3", credentials=creds)
    event = {"summary": summary, "start": {"dateTime": start}, "end": {"dateTime": end}}
    if description: event["description"] = description
    if location: event["location"] = location
    created = svc.events().insert(calendarId="primary", body=event).execute()
    await log("INFO", "google_tools", f"Created event {created['id']}")
    return created

@mcp.tool()
async def calendar_update(event_id: str, updates: dict):
    """
    Updates an existing calendar event with the specified updates.
    `event_id` is the ID of the event to update, and `updates` is a dictionary of fields to update.
    Allowed fields in `updates` include: summary, start, end, description, location.
    Returns the updated event details.
    """
    
    creds = get_credentials(CALENDAR_SCOPES)
    svc = build("calendar", "v3", credentials=creds)
    updated = svc.events().patch(calendarId="primary", eventId=event_id, body=updates).execute()
    await log("INFO", "google_tools", f"Updated event {event_id}")
    return updated

@mcp.tool()
async def calendar_delete(event_id: str):
    """
    Deletes a calendar event by its ID.
    `event_id` should be the full event ID string.
    Returns a confirmation message.
    """

    creds = get_credentials(CALENDAR_SCOPES)
    svc = build("calendar", "v3", credentials=creds)
    svc.events().delete(calendarId="primary", eventId=event_id).execute()
    await log("INFO", "google_tools", f"Deleted event {event_id}")
    return {"status": "deleted", "id": event_id}

# --- Contacts operations ---

@mcp.tool()
async def contacts_find_by_name(name: str):
    """
    Searches for a contact by display name and returns its resourceName.
    If no contact is found, returns an error string.
    """
    creds = get_credentials(CONTACTS_SCOPES)
    svc = build("people", "v1", credentials=creds)
    connections = svc.people().connections().list(
        resourceName="people/me",
        personFields="names,emailAddresses,phoneNumbers",
        pageSize=2000
    ).execute()

    for person in connections.get("connections", []):
        for n in person.get("names", []):
            if n.get("displayName", "").lower() == name.lower():
                return person["resourceName"]
    return f"No contact found with name '{name}'"


@mcp.tool()
async def contacts_get_by_name(name: str):
    """
    Returns full contact info by display name or error string if not found.
    """
    creds = get_credentials(CONTACTS_SCOPES)
    svc = build("people", "v1", credentials=creds)
    connections = svc.people().connections().list(
        resourceName="people/me",
        personFields="names,emailAddresses,phoneNumbers,organizations",
        pageSize=2000
    ).execute()

    for person in connections.get("connections", []):
        for n in person.get("names", []):
            if n.get("displayName", "").lower() == name.lower():
                return person
    return f"No contact found with name '{name}'"


@mcp.tool()
async def contacts_create_contact(givenName: str, familyName: str, email: str = None, phone: str = None):
    """
    Creates a new contact with given info. If a contact with the same name exists, returns an error.
    """
    existing = await contacts_find_by_name(f"{givenName} {familyName}")
    if isinstance(existing, str) and existing.startswith("people/"):
        return {"error": f"Contact '{givenName} {familyName}' already exists."}

    creds = get_credentials(CONTACTS_SCOPES)
    svc = build("people", "v1", credentials=creds)
    person = {
        "names": [{"givenName": givenName, "familyName": familyName}]
    }
    if email:
        person["emailAddresses"] = [{"value": email}]
    if phone:
        person["phoneNumbers"] = [{"value": phone}]

    created = svc.people().createContact(body=person).execute()
    await log("INFO", "google_tools", f"Created contact {created['resourceName']}")
    return created


@mcp.tool()
async def contacts_update_contact(identifier: str, updates: dict):
    """
    Updates an existing contact.
    `identifier` can be resourceName like 'people/abc123' or display name.
    `updates` must be a dict of allowed fields only.
    """
    if not updates or not isinstance(updates, dict):
        return {"error": "Missing or invalid updates dictionary."}

    allowed_fields = {"names", "emailAddresses", "phoneNumbers"}
    for key in updates:
        if key not in allowed_fields:
            return {"error": f"Cannot update field '{key}'. Allowed fields: {', '.join(allowed_fields)}"}

    creds = get_credentials(CONTACTS_SCOPES)
    svc = build("people", "v1", credentials=creds)

    resource_name = identifier
    if not identifier.startswith("people/"):
        found = await contacts_find_by_name(identifier)
        if not found.startswith("people/"):
            return {"error": f"Contact not found: {identifier}"}
        resource_name = found

    update_fields = ",".join(updates.keys())
    updated = svc.people().updateContact(
        resourceName=resource_name,
        updatePersonFields=update_fields,
        body=updates
    ).execute()
    await log("INFO", "google_tools", f"Updated contact {resource_name}")
    return updated


@mcp.tool()
async def contacts_delete_contact(identifier: str):
    """
    Deletes a contact by resourceName or display name.
    """
    creds = get_credentials(CONTACTS_SCOPES)
    svc = build("people", "v1", credentials=creds)

    resource_name = identifier
    if not identifier.startswith("people/"):
        found = await contacts_find_by_name(identifier)
        if not found.startswith("people/"):
            return {"error": f"Contact not found: {identifier}"}
        resource_name = found

    svc.people().deleteContact(resourceName=resource_name).execute()
    await log("INFO", "google_tools", f"Deleted contact {resource_name}")
    return {"status": "deleted", "resourceName": resource_name}

# --- Tasks operations ---
@mcp.tool()
async def tasks_find_by_title(title: str, tasklist_id: str = "@default") -> str:
    """
    Searches for a task in the given tasklist by title (case-insensitive) and returns its task ID.
    """
    if tasklist_id.lower() == "default":
        tasklist_id = "@default"

    creds = get_credentials(TASKS_SCOPES)
    svc = build("tasks", "v1", credentials=creds)

    try:
        tasks = svc.tasks().list(tasklist=tasklist_id).execute().get("items", [])
        for task in tasks:
            if task.get("title", "").strip().lower() == title.strip().lower():
                return task["id"]
        raise HTTPException(status_code=404, detail={"message": f"Task titled '{title}' not found."})
    except Exception as e:
        await log("ERROR", "google_tools", f"Unexpected error calling tasks_find_by_title: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail={"message": f"Error finding task: {e}"})
    
@mcp.tool()
async def tasks_list_tasklists():
    """
    Lists all Google Tasks tasklists.
    Returns a list of dictionaries with tasklist ID and title.
    """
    creds = get_credentials(TASKS_SCOPES)
    svc = build("tasks", "v1", credentials=creds, cache_discovery=False)
    tasklists = svc.tasklists().list().execute().get("items", [])
    await log("INFO", "google_tools", f"Listed {len(tasklists)} tasklists")
    return [{"id": t["id"], "title": t["title"]} for t in tasklists]

@mcp.tool()
async def tasks_list(max_results: int = 20):
    """ Lists tasks from the default tasklist. """
    creds = get_credentials(TASKS_SCOPES)
    svc = build("tasks", "v1", credentials=creds, cache_discovery=False)

    tasklist_id = "@default"

    try:
        lst = svc.tasks().list(tasklist=tasklist_id, maxResults=max_results).execute()
        items = lst.get("items", [])
        await log("INFO", "google_tools", f"Fetched {len(items)} tasks from {tasklist_id}")
        return items
    except Exception as e:
        await log("ERROR", "google_tools", f"Invalid tasklist_id '{tasklist_id}': {e}")
        raise HTTPException(status_code=400, detail=f"Invalid task list ID '{tasklist_id}'")

@mcp.tool()
async def tasks_add(title: str, notes: str = None, due: str = None):
    """
    Creates a new task in the default tasklist.
    `title` is the task title, `notes` is optional task notes,
    and `due` is an optional due date in RFC3339 format (e.g., "2025-07-21T23:59:00-04:00").
    """
    
    tasklist_id = "@default"
    creds = get_credentials(TASKS_SCOPES)
    svc = build("tasks", "v1", credentials=creds, cache_discovery=False)

    body = {"title": title}
    if notes: body["notes"] = notes
    if due: body["due"] = due
    created = svc.tasks().insert(tasklist=tasklist_id, body=body).execute()
    await log("INFO", "google_tools", f"Created task {created['id']}")
    return created

@mcp.tool()
async def tasks_update_by_title(
    title: str,
    status: Optional[str] = None,
    new_title: Optional[str] = None,
    notes: Optional[str] = None,
    due: Optional[str] = None,
    tasklist_id: str = "@default"
):
    """
    Updates a Google Task using its title. Optional fields to update: status, new_title, notes, due date.
    `status` can be "needsAction" or "completed".
    `due` must be an RFC3339 timestamp with time zone offset (e.g., "2025-07-21T23:59:00-04:00").
    """
    if tasklist_id.lower() == "default":
        tasklist_id = "@default"

    creds = get_credentials(TASKS_SCOPES)
    svc = build("tasks", "v1", credentials=creds, cache_discovery=False)

    try:
        tasks = svc.tasks().list(tasklist=tasklist_id).execute().get("items", [])
        match = next((t for t in tasks if t.get("title", "").strip().lower() == title.strip().lower()), None)

        if not match:
            raise HTTPException(status_code=404, detail={"message": f"Task titled '{title}' not found."})

        task_id = match["id"]

        updates = {}
        if status: updates["status"] = status
        if new_title: updates["title"] = new_title
        if notes: updates["notes"] = notes
        if due: updates["due"] = due

        updated = svc.tasks().patch(tasklist=tasklist_id, task=task_id, body=updates).execute()
        return {"message": f"Task '{title}' updated successfully.", "updated_task": updated}

    except Exception as e:
        await log("ERROR", "google_tools", f"Unexpected error in tasks_update_by_title: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail={"message": f"Error updating task '{title}': {e}"})


@mcp.tool()
async def tasks_delete(task_id: str):
    """
    Deletes a task by its ID from the default tasklist.
    `task_id` should be the full task ID string.
    Returns a confirmation message.
    """

    tasklist_id = "@default"
    creds = get_credentials(TASKS_SCOPES)
    svc = build("tasks", "v1", credentials=creds, cache_discovery=False)

    svc.tasks().delete(tasklist=tasklist_id, task=task_id).execute()
    await log("INFO", "google_tools", f"Deleted task {task_id}")
    return {"status": "deleted", "id": task_id}