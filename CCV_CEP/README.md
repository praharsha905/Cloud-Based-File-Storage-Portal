# Cloud-Based File Storage Portal (Course End Project)

A complete starter implementation of a cloud-style file storage portal built with Flask + SQLite.

## Features
- User registration and login with hashed passwords
- Personal dashboard with storage usage tracking
- Upload, download, and delete files
- File metadata persistence in SQLite
- Secure expiring share links (1 to 30 days)
- Responsive UI for desktop and mobile

## Tech Stack
- Python 3.10+
- Flask
- SQLite
- HTML/CSS with Jinja templates

## Project Structure
```text
CCV_CEP/
  app.py
  requirements.txt
  templates/
  static/
  data/
    uploads/
```

## Setup and Run (PowerShell)
1. Create virtual environment:
   ```powershell
   python -m venv .venv
   ```
2. Install dependencies:
   ```powershell
   .\.venv\Scripts\python -m pip install -r requirements.txt
   ```
3. (Optional) Set a stronger secret key:
   ```powershell
   $env:SECRET_KEY = "replace-with-strong-secret"
   ```
4. Run app:
   ```powershell
   .\.venv\Scripts\python app.py
   ```
5. Open browser:
   - http://127.0.0.1:5000

## Notes for Viva / Demo
- New users get 100 MB quota by default.
- Max upload size per file is 25 MB.
- Shared links are public and time-limited.
- Runtime data is stored under `data/`.

## Suggested Next Enhancements
- Email verification and password reset
- Admin panel for quota management
- Virus scan hook for uploaded files
- Cloud object storage integration (S3 / GCS / Azure Blob)
- Role-based access and team folders
