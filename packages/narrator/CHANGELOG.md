## [narrator-v5.2.0] - 2025-11-04

### 🚀 Features

- Replace python-magic with filetype for pure-Python MIME detection
## [tyler-v3.0.0] - 2025-10-15

### 🚀 Features

- Add reasoning_content as top-level field in Narrator Message
## [tyler-v2.2.3] - 2025-10-14

### 🐛 Bug Fixes

- Add typing_extensions for Python 3.11 compatibility
## [narrator-v1.0.2] - 2025-08-15

### 💼 Other

- Fix MemoryBackend search; sanitize JSON path queries; correct SQL JSON path building; remove dead data-URL code; make logging library-friendly; update python requires; trim deps
- Add tests for message search accumulation, JSON path handling, and key sanitization
- Extend SQLite handling for bool/null in JSON queries; add tests for attrs/platforms, attachment URL, logging, list_files, and attachment dedup
- Address review — move re import to module scope; avoid param for SQLite json_path; improve default logger name hierarchy
## [narrator-v0.4.0] - 2025-08-08

### 📚 Documentation

- Standardize installation to uv-first across repo
## [space-monkey-v0.2.0] - 2025-07-25
