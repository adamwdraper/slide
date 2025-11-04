# Impact Analysis — Remove libmagic System Dependency

## Modules/packages likely touched

### Core Implementation Files (3 files)
- `packages/lye/lye/files.py` - Replace `magic.from_buffer()` calls with `filetype.guess_mime()`
- `packages/narrator/narrator/storage/file_store.py` - Replace MIME detection in file validation
- `packages/narrator/narrator/models/attachment.py` - Replace MIME detection in attachment processing (3 locations: `from_file_path()`, `detect_mime_type()`, `process_and_store()`)

### Dependency Files (4 files)
- `packages/lye/pyproject.toml` - Replace `python-magic>=0.4.0` with `filetype>=1.2.0`
- `packages/narrator/pyproject.toml` - Replace `python-magic>=0.4.0` with `filetype>=1.2.0`
- `packages/tyler/pyproject.toml` - Replace `python-magic>=0.4.27` with `filetype>=1.2.0`
- `uv.lock` - Will be regenerated after pyproject.toml updates

### Test Files (1 file)
- `tests/test_examples.py` - Remove 9 test skips related to libmagic dependency (lines 35-48)

### Documentation Files (7 files)
- `docs/guides/your-first-agent.mdx` - Remove libmagic installation instructions (line 435)
- `docs/standalone-packages/using-lye.mdx` - Remove libmagic installation instructions (line 32)
- `docs/packages/lye/introduction.mdx` - Remove libmagic from system requirements (lines 102-108)
- `docs/guides/adding-tools.mdx` - Remove libmagic troubleshooting section (lines 297-299)
- `packages/tyler/README.md` - Remove libmagic from installation instructions (lines 150-153)
- `packages/narrator/README.md` - Remove system dependencies mention (line 504)
- `packages/lye/README.md` - Remove libmagic installation instructions (lines 90-93)
- `examples/DEVELOPMENT.md` - Remove libmagic troubleshooting section (lines 192-203)

**Total affected files: 15**

## Contracts to update (APIs, events, schemas, migrations)

### Public APIs
**No breaking changes** - All public function signatures remain identical:
- `lye.files.read_file(file_url, mime_type)` - unchanged
- `Attachment.from_file_path(file_path)` - unchanged
- `Attachment.detect_mime_type()` - unchanged
- `FileStore.validate_file(content, filename, mime_type)` - unchanged

### Internal Implementation
- MIME detection calls change from `magic.from_buffer(content, mime=True)` to `filetype.guess_mime(content)`
- Fallback logic updated to use `mimetypes.guess_type()` when `filetype` returns `None`

### Schemas
- No database schema changes
- No message format changes
- No storage format changes

### Migrations
- No migrations required
- Existing stored files continue working without changes

## Risks

### Security
- **Low Risk**: Both libraries perform content-based file type detection
- `python-magic` (current): Binds to libmagic C library, which has CVE history (though rare)
- `filetype` (new): Pure Python implementation, smaller attack surface, no native code vulnerabilities
- **Mitigation**: `filetype` is actively maintained (1.2M+ downloads/month), well-tested
- **Action**: Include in standard dependency security scanning

### Performance/Availability
- **Low Risk**: Performance characteristics should be similar or better
- `filetype` is optimized for common file types with byte signature matching
- No external process calls (unlike libmagic which calls system library)
- Potential edge case: Very large files (>50MB) - but we already have file size limits
- **Mitigation**: 
  - Add performance logging for MIME detection calls during testing
  - Existing file size limits (50MB default) prevent performance issues
- **Fallback**: `mimetypes.guess_type()` as secondary detection method

### Data integrity
- **Medium Risk**: Different MIME type detection for edge cases
- Core file types (PDF, PNG, JPEG, TXT, CSV, JSON) are well-supported by both libraries
- Potential differences for:
  - Obscure/custom file formats
  - Files with ambiguous byte signatures
  - Empty or malformed files
- **Mitigation**:
  - Comprehensive test suite covering all supported MIME types in `FileStore.DEFAULT_ALLOWED_MIME_TYPES`
  - Graceful fallback to `mimetypes.guess_type()` when `filetype` returns `None`
  - Default to `application/octet-stream` as safe fallback
  - Add test cases for edge cases (empty files, corrupted files)
- **Testing Strategy**:
  ```python
  # Test all currently allowed MIME types
  MIME_TYPES_TO_TEST = [
      'application/pdf',
      'image/jpeg', 'image/png', 'image/gif', 'image/webp',
      'text/plain', 'text/csv',
      'application/json',
      'audio/mpeg', 'audio/wav', 'audio/ogg',
      # etc.
  ]
  ```

### Backward Compatibility
- **Low Risk**: Internal implementation change only
- Existing user code doesn't directly call MIME detection
- File storage format unchanged
- Previously stored files remain accessible
- **Verification**: Run full test suite including integration tests

## Observability needs

### Logs
**Existing logging is sufficient** - Current debug-level logging already captures:
- `packages/lye/lye/files.py:48` - "Detected MIME type for {filename}: {mime_type}"
- `packages/narrator/narrator/storage/file_store.py:289` - "Detected MIME type for {filename}: {mime_type}"
- `packages/narrator/narrator/models/attachment.py:213` - "Detected MIME type: {detected_mime_type}"

**No new logging required**, but ensure existing logs remain:
- MIME type detection results (debug level)
- Fallback to mimetypes when filetype returns None (debug level)
- MIME type mismatch warnings (warning level)
- File validation errors (error level)

### Metrics
**No new metrics required** - Existing error rates will capture issues:
- File processing errors already tracked via exception handling
- Test suite metrics will show any regressions
- No performance SLOs exist for MIME detection currently

**Optional enhancement** (non-blocking):
- Add timing metrics for MIME detection if performance concerns arise during testing

### Alerts
**No new alerts required** - Existing error handling covers failure cases:
- `UnsupportedFileTypeError` - already raised for invalid MIME types
- `FileTooLargeError` - already raised for size violations
- General exceptions - already logged and raised appropriately

**Monitoring strategy**:
- Rely on existing test suite to catch MIME detection regressions
- Monitor for increased error rates after deployment via existing observability
- No specialized alerting needed for this dependency change

