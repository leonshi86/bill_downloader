# Copilot Instructions for bill_downloader

- This is a small Python desktop app for downloading email attachments via IMAP.
- `main.py` is the application entrypoint. It only sets up logging and then calls `main_window.main()`.
- `main_window.py` contains the entire PySide6 GUI and a `DownloadThread` wrapper around `EmailDownloader`.
- `email_downloader.py` contains the core IMAP logic, including server detection, login, email searching, attachment filtering, and file saving.
- `config.py` handles JSON config persistence in `config.json` and merges defaults from `DEFAULT_CONFIG`.

### Architecture and responsibilities
- `main_window.py` is UI-only: form layout, input validation, tray behavior, and threading.
- `email_downloader.py` is the business logic: connect/login/select inbox/search messages/download attachments.
- Communication between UI and logic is callback-based:
  - `EmailDownloader` accepts `progress_callback`, `status_callback`, `save_callback`, and `stop_flag`.
  - `DownloadThread` emits Qt signals for progress, current file, logs, and completion.
- `EmailDownloader.run()` returns `(downloaded_count, skipped_count)`.

### Key patterns and project-specific details
- IMAP server is inferred from the email domain in `EmailDownloader._imap_server()`.
- `subject_keywords` are combined as OR conditions in IMAP search.
- Allowed attachment extensions are normalized to lowercase and checked with `filename.lower().endswith(ext)`.
- UI uses a frameless window and custom QSS styling defined in `main_window.py`.
- The app persists user settings in `config.json` under the same directory as `config.py`.
- Password login is present in the UI but disabled; the app expects IMAP authorization codes.

### Run / build workflows
- Install dependencies: `pip install PySide6`.
- Run locally: `python main.py`.
- Build Windows EXE: `pip install pyinstaller` then `pyinstaller bill_downloader.spec`.
- There are no automated tests or CI files in this repo.

### Helpful file references
- `main.py`: startup logic
- `main_window.py`: Qt UI, thread orchestration, config load/save
- `email_downloader.py`: IMAP connection, email search, attachment save logic
- `config.py`: default config shape and persistence
- `bill_downloader.spec`: PyInstaller packaging settings
- `README.md`: user-facing usage and packaging instructions

### When editing
- Preserve the existing callback/signal contract between `DownloadThread` and `EmailDownloader`.
- Keep UI logic in `main_window.py` and avoid moving IMAP code into the GUI module.
- Do not assume a config file exists; use `load_config()` fallback behavior.
- Avoid changing the app's default `.pdf` attachment-only behavior unless explicitly updating `allow_exts` handling.
