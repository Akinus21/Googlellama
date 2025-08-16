# Googlellama

Googlellama is an asynchronous MCP (Modular Command Processing) server for managing **Gmail, Google Calendar, Contacts, and Tasks** via the Google APIs.  
It provides a collection of ready-to-use MCP tools that can be invoked programmatically or through prompts from an LLM.  

The library is designed for automation, batch processing, and intelligent integrations, allowing you to clean up inboxes, manage events, update contacts, and automate tasks efficiently.

---

## **Features**

### Gmail Tools
- `clean_up_inbox` — Batch clean and archive your inbox.
- `clean_up_archive` — Remove old or unwanted archived messages.
- `add_sender_to_delete_list` / `add_sender_to_archive_list` — Manage sender filters.
- `gmail_list` — List emails with metadata (subject, sender, date).
- `delete_multiple_emails` — Bulk delete emails by query.
- `gmail_send` — Send emails programmatically.
- `gmail_modify` — Add or remove labels from messages.
- `gmail_delete` / `gmail_archive` — Delete or archive individual messages.

### Google Calendar Tools
- `calendar_list` — List upcoming events in a specified time range.
- `calendar_add` — Create a new calendar event.
- `calendar_update` — Update an existing calendar event.
- `calendar_delete` — Delete a calendar event by ID.

### Contacts Tools
- `contacts_find_by_name` / `contacts_get_by_name` — Search contacts by name.
- `contacts_create_contact` — Create new contacts.
- `contacts_update_contact` — Update existing contacts.
- `contacts_delete_contact` — Delete contacts.

### Google Tasks Tools
- `tasks_find_by_title` — Find tasks by title.
- `tasks_list_tasklists` — List all tasklists.
- `tasks_list` — List tasks from the default tasklist.
- `tasks_add` — Add a new task.
- `tasks_update_by_title` — Update tasks by title.
- `tasks_delete` — Delete tasks by ID.

---

## **Installation**

Install globally in editable mode (no virtual environment required):

```bash
# Exit any virtual environment first
deactivate  # if inside a venv

# Install
pip install --user -e .
```

Ensure your PATH includes `~/.local/bin` (Linux/macOS):

```bash
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Verify installation:

```bash
which Googlellama
Googlellama --help
```

---

## **Usage Examples**

Googlellama is intended for MCP integration, typically invoked via an LLM or script that interacts with MCP tools.

### **Example 1: Clean up your inbox**

```python
import asyncio
from Googlellama import google_tools

asyncio.run(google_tools.clean_up_inbox())
```

- Cleans and deduplicates your filters.
- Adds senders labeled 'Delete' to `delete_filter.txt`.
- Deletes matching emails in batches.
- Archives matching and read emails.

---

### **Example 2: Send an email**

```python
await google_tools.gmail_send(
    to="recipient@example.com",
    subject="Hello from Googlellama",
    body="This email was sent via MCP automation."
)
```

---

### **Example 3: List upcoming calendar events**

```python
events = await google_tools.calendar_list(max_results=5)
for event in events:
    print(event['summary'], event['start']['dateTime'])
```

---

### **Example 4: Add a new contact**

```python
await google_tools.contacts_create_contact(
    givenName="Alice",
    familyName="Smith",
    email="alice.smith@example.com"
)
```

---

### **Example 5: Create a new task**

```python
await google_tools.tasks_add(
    title="Finish MCP integration",
    notes="Complete all Gmail and Calendar tools integration",
    due="2025-08-31T17:00:00-04:00"
)
```

---

## **LLM / Prompt Integration**

This MCP server is intended to be invoked via an LLM.  
You can create prompts like:

- "Clean up all emails from senders in the delete list"
- "Send an email to Bob with subject 'Reminder' and body 'Don't forget the meeting!'"
- "List my upcoming calendar events for the next week"
- "Create a new contact Alice Smith with email alice@example.com"

---

## **Configuration**

1. Place your Google API credentials in `data/credentials.json`.
2. The OAuth token will be stored in `data/token.json` after the first authorization.
3. Filters for deleting/archiving emails are stored in:
   - `data/delete_filter.txt`
   - `data/archive_filter.txt`

---

## **Development**

Editable installation allows instant testing:

```bash
pip install --user -e .
```

All changes to Python source files are immediately available without reinstalling.

---

## **Requirements**

- Python >= 3.10
- `requests`, `google-api-python-client`, `google-auth-oauthlib`, `fastapi`, `mcp`, `dotenv`, etc. (installed automatically via pip).

---

## **License**

MIT License © Akinus21

---

