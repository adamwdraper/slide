# Technical Design Review (TDR) — Remove libmagic System Dependency

**Author**: AI Agent  
**Date**: 2025-11-04  
**Links**: 
- Spec: `/directive/specs/remove-libmagic-dependency/spec.md`
- Impact: `/directive/specs/remove-libmagic-dependency/impact.md`

---

## 1. Summary

We are replacing the `python-magic` library (which requires the `libmagic1` system dependency) with `filetype`, a pure-Python library for MIME type detection. This eliminates the need for users to install system-level packages (via brew/apt) before using Slide framework.

Currently, three packages (`lye`, `narrator`, `tyler`) depend on `python-magic` for content-based MIME type detection when processing files. This creates installation friction, test failures, and deployment complexity. By switching to `filetype`, we maintain identical functionality while providing a smoother installation experience with standard Python tooling.

## 2. Decision Drivers & Non‑Goals

**Drivers:**
- **User Experience**: Eliminate installation friction - users should be able to install with just `pip install` or `uv add`
- **Testing Reliability**: Remove 9 skipped test cases caused by libmagic dependency issues
- **Deployment Simplicity**: Reduce Docker image complexity and cross-platform deployment issues
- **Maintenance**: Pure Python dependencies are easier to manage and debug than system dependencies

**Non‑Goals:**
- Adding new file type support beyond current capabilities
- Performance optimization (though improvements are welcome as side effects)
- Changing file storage architecture or processing pipelines
- Adding validation beyond MIME type detection
- Supporting additional file metadata extraction

## 3. Current State — Codebase Map (concise)

### Key modules using python-magic

1. **`packages/lye/lye/files.py`**
   - Function: `read_file()` - Smart file reading with auto-format detection
   - Line 48: `mime_type = magic.from_buffer(content, mime=True)`
   - Usage: Detects MIME type when not provided by caller

2. **`packages/narrator/narrator/storage/file_store.py`**
   - Class: `FileStore`
   - Method: `validate_file()` - File validation before storage
   - Line 288: `mime_type = magic.from_buffer(content, mime=True)`
   - Usage: Content-based MIME detection as fallback when filename-based detection fails

3. **`packages/narrator/narrator/models/attachment.py`**
   - Class: `Attachment`
   - Methods: `from_file_path()` (line 64), `detect_mime_type()` (line 91), `process_and_store()` (line 212)
   - Three locations using `magic.from_buffer(content, mime=True)`
   - Usage: MIME detection for message attachments

### Data models

- **FileStore metadata dict**: `{'id', 'filename', 'mime_type', 'storage_path', 'storage_backend', 'created_at', 'metadata'}`
- **Attachment model**: Pydantic model with fields: `filename`, `content`, `mime_type`, `attributes`, `file_id`, `storage_path`, `storage_backend`, `status`
- **File limits**: 
  - `DEFAULT_MAX_FILE_SIZE = 50MB`
  - `DEFAULT_ALLOWED_MIME_TYPES` = 18 MIME types (documents, images, archives, audio)

### External contracts

- **Tool APIs**: `files-read_file`, `files-write_file` (defined in lye/files.py:440-495)
- **FileStore API**: `save()`, `get()`, `delete()`, `validate_file()`
- **Attachment API**: `from_file_path()`, `detect_mime_type()`, `process_and_store()`, `get_content_bytes()`

None of these public APIs expose MIME detection directly - it's all internal implementation.

### Observability

- Debug-level logging exists for MIME detection results
- Warning-level logging for MIME type mismatches
- Error-level logging for file processing failures
- No specific metrics for MIME detection performance

## 4. Proposed Design (high level, implementation‑agnostic)

### Overall Approach

Replace `import magic` with `import filetype` and update MIME detection logic with a two-tier fallback strategy:

1. **Primary**: `filetype.guess_mime(content)` - Content-based detection via byte signatures
2. **Fallback**: `mimetypes.guess_type(filename)` - Extension-based detection
3. **Default**: `application/octet-stream` - Safe default for unknown types

### Component Responsibilities

**lye.files module:**
- Detect MIME type when reading files if not provided
- Route files to appropriate processors (PDF, CSV, JSON, text)
- Maintain existing API contract

**narrator.file_store module:**
- Validate uploaded files against allowed MIME types
- Detect MIME type from content when filename-based detection fails
- Store file metadata with detected MIME type

**narrator.attachment module:**
- Detect MIME type for attachments created from file paths
- Process attachments based on detected MIME type (image, audio, PDF, text, etc.)
- Store attachments with correct MIME type metadata

### Interface Contract

```python
# Current interface (unchanged)
def detect_mime_type(content: bytes, filename: str) -> str:
    """Detect MIME type from file content"""
    pass

# New implementation
def detect_mime_type(content: bytes, filename: str) -> str:
    """Detect MIME type from file content with fallback strategy"""
    # Primary: content-based detection
    mime_type = filetype.guess_mime(content)
    
    if not mime_type:
        # Fallback: extension-based detection
        mime_type, _ = mimetypes.guess_type(filename)
    
    if not mime_type:
        # Default: binary
        mime_type = 'application/octet-stream'
    
    return mime_type
```

### Error Handling

**Existing behavior preserved:**
- `UnsupportedFileTypeError` - when detected MIME type not in allowed list
- `FileTooLargeError` - when file exceeds size limits
- Generic `RuntimeError` - for processing failures

**New edge cases:**
- Empty files: `filetype.guess_mime()` returns `None` → fallback to `mimetypes`
- Corrupted files: `filetype` returns `None` → fallback to `mimetypes` → default to `application/octet-stream`
- No exceptions thrown for detection failures - always return a MIME type

### Performance Expectations

- `filetype` reads first ~8KB of file for signature matching (comparable to libmagic)
- No performance degradation expected for files under 50MB (our limit)
- Fallback to `mimetypes` is nearly instant (dict lookup)
- No synchronous I/O blocking beyond current behavior

## 5. Alternatives Considered

### Option A: python-magic-bin (Chosen Alternative)
**Description**: Use `python-magic-bin` which bundles libmagic binaries within the Python package

**Pros:**
- Minimal code changes (same API as python-magic)
- Leverages battle-tested libmagic library
- No system dependency installation required

**Cons:**
- Larger package size (~2-5MB depending on platform)
- Still relies on binary dependencies (just bundled)
- Binary compatibility issues across platforms
- Less maintained than core python-magic
- Security updates require package updates

### Option B: filetype (CHOSEN)
**Description**: Pure Python library using byte signature matching

**Pros:**
- ✅ Zero system dependencies
- ✅ Pure Python - easier to debug and maintain
- ✅ Smaller package footprint
- ✅ Well-maintained (1.2M+ downloads/month)
- ✅ Fast for common file types
- ✅ Cross-platform consistency guaranteed

**Cons:**
- Less comprehensive than libmagic for obscure formats
- May miss some edge cases in custom/proprietary formats

**Why chosen:** Covers all currently supported MIME types, eliminates system dependencies entirely, and provides better cross-platform consistency. The fallback strategy mitigates edge case concerns.

### Option C: Use mimetypes only
**Description**: Rely solely on Python's built-in `mimetypes` module (extension-based)

**Pros:**
- No external dependencies at all
- Part of Python standard library

**Cons:**
- ❌ No content-based detection - relies solely on file extensions
- ❌ Easily fooled by renamed files (e.g., `.exe` renamed to `.txt`)
- ❌ Security risk - can't validate actual file contents
- ❌ Breaks existing functionality that relies on content detection

**Why rejected:** Insufficient for security and validation purposes. Content-based detection is required.

### Option D: Custom byte signature detection
**Description**: Implement our own byte signature matching for supported types

**Pros:**
- Full control over detection logic
- No external dependencies

**Cons:**
- ❌ Reinventing the wheel
- ❌ Maintenance burden for signature database
- ❌ Higher risk of bugs and edge cases
- ❌ Significant development time

**Why rejected:** `filetype` already provides this functionality with better testing and maintenance.

## 6. Data Model & Contract Changes

### Tables/Collections
**No database schema changes required**
- Existing `mime_type` fields remain unchanged
- File metadata storage format unchanged
- No migrations needed

### API Changes
**No breaking changes to public APIs**

All function signatures remain identical:
```python
# lye/files.py
async def read_file(*, file_url: str, mime_type: Optional[str] = None) -> Tuple[Dict, List]
async def write_file(content: Any, file_url: str, mime_type: Optional[str] = None) -> Tuple[Dict, List]

# narrator/storage/file_store.py
async def validate_file(self, content: bytes, filename: str, mime_type: Optional[str] = None) -> str
async def save(self, content: bytes, filename: str, mime_type: Optional[str] = None) -> Dict[str, Any]

# narrator/models/attachment.py
@classmethod
def from_file_path(cls, file_path: Union[str, Path]) -> 'Attachment'
def detect_mime_type(self) -> None
async def process_and_store(self, file_store: FileStore, force: bool = False) -> None
```

### Internal Implementation Changes
```python
# OLD
import magic
mime_type = magic.from_buffer(content, mime=True)

# NEW
import filetype
mime_type = filetype.guess_mime(content)
if not mime_type:
    mime_type, _ = mimetypes.guess_type(filename)
if not mime_type:
    mime_type = 'application/octet-stream'
```

### Backward Compatibility
- ✅ Existing code using file tools continues working without changes
- ✅ Previously stored files remain accessible (storage format unchanged)
- ✅ MIME types for common formats remain consistent
- ⚠️ Edge case: Obscure file formats may get different MIME types (acceptable - fallback handles this)

### Deprecation Plan
**No deprecation needed** - This is an internal dependency swap with no public API changes.

## 7. Security, Privacy, Compliance

### AuthN/AuthZ
- **No changes** to authentication or authorization models
- File access controls remain unchanged

### Secrets Management
- **Not applicable** - no secrets involved in MIME detection

### PII Handling
- **No changes** to PII handling
- File content is not logged (existing behavior preserved)
- MIME types and filenames logged at debug level (existing behavior)

### Threat Model & Mitigations

**Threat 1: Malicious File Upload (MIME Spoofing)**
- **Risk**: Attacker uploads malicious file with fake extension (e.g., `.exe` as `.txt`)
- **Current mitigation**: Content-based detection via libmagic
- **New mitigation**: Content-based detection via filetype + extension validation
- **Impact**: Security posture maintained or improved (pure Python = smaller attack surface)

**Threat 2: Dependency Vulnerabilities**
- **Risk**: Vulnerabilities in MIME detection library
- **Current**: libmagic has CVE history (rare but exists), native C library
- **New**: filetype is pure Python with no native code, smaller attack surface
- **Impact**: Reduced risk of memory-related vulnerabilities

**Threat 3: Denial of Service (Large Files)**
- **Risk**: Large files causing excessive processing during MIME detection
- **Mitigation**: Existing file size limits (50MB default) prevent this
- **Note**: filetype only reads first ~8KB for signature matching (efficient)

**Threat 4: File Type Confusion**
- **Risk**: Incorrect MIME detection leading to improper file handling
- **Mitigation**: 
  - Fallback to mimetypes for additional validation
  - Allowed MIME type whitelist (`DEFAULT_ALLOWED_MIME_TYPES`)
  - Comprehensive test coverage for all supported types

**Overall Security Impact**: Neutral to positive (smaller attack surface, no native code vulnerabilities)

## 8. Observability & Operations

### Logs to Maintain (existing)

**Debug level:**
```python
logger.debug(f"Detected MIME type for {filename}: {mime_type}")
logger.debug(f"MIME type already set for {filename}: {self.mime_type}")
```

**Warning level:**
```python
logger.warning(f"Provided MIME type {self.mime_type} doesn't match detected type {detected_mime_type}")
```

**Error level:**
```python
logger.error(f"Error reading file {file_url}: {str(e)}")
logger.error(f"Failed to process attachment {filename}: {str(e)}")
```

### New Logs (optional, for debugging transition)
```python
# Could add temporarily for monitoring the switch
logger.debug(f"filetype returned None, falling back to mimetypes for {filename}")
```

### Metrics
**No new metrics required**
- File processing error rates (existing)
- Test pass/fail rates (existing)

**Optional monitoring during rollout:**
- Track frequency of fallback to mimetypes (indicates filetype coverage gaps)

### Dashboards
- **No dashboard changes required**
- Existing error monitoring dashboards remain relevant

### Alerts
- **No new alerts required**
- Existing error rate alerts will catch any issues

### SLOs
- **No SLOs defined** for MIME detection currently
- File processing SLOs (if any) remain unchanged

### Runbooks
**No runbook changes needed** - Same error handling and troubleshooting procedures apply.

## 9. Rollout & Migration

### Feature Flags
**Not required** - This is a dependency swap with:
- No runtime configuration needed
- No gradual rollout complexity
- Instant switch on deployment

### Rollout Strategy
1. **Development**: Test locally with new dependency
2. **CI**: All tests must pass including previously skipped tests
3. **Staging** (if applicable): Deploy and monitor for 24hrs
4. **Production**: Standard deployment

### Data Migration
**Not required** - No data model changes, no stored data affected

### Guardrails
- Full test suite must pass (including integration tests)
- Manual smoke testing of file upload/processing in examples
- Monitor error rates for first 48hrs after deployment

### Revert Plan
**Low risk, simple revert:**
1. Revert the PR (single commit or squashed commits)
2. Restore `python-magic` dependencies
3. Redeploy
4. **Time to revert**: < 15 minutes

**Blast Radius**: Limited to file processing functionality
- File reading/writing
- Attachment processing
- MIME type validation

**Mitigation**: All existing stored files remain accessible (no data migration means no rollback complexity)

## 10. Test Strategy & Spec Coverage (TDD)

### TDD Commitment
✅ **Write failing tests first** for each MIME type before implementing changes
✅ **Confirm tests fail** with python-magic removed but filetype not yet integrated
✅ **Implement changes** to make tests pass
✅ **Refactor** for code quality while keeping tests green

### Spec→Test Mapping

| Spec Acceptance Criterion | Test ID(s) | Test Tier |
|---------------------------|-----------|-----------|
| PDF file detected as `application/pdf` | `test_detect_mime_pdf` | Unit |
| PNG image detected as `image/png` | `test_detect_mime_png` | Unit |
| Text file detected as `text/plain` | `test_detect_mime_text` | Unit |
| Unknown binary → `application/octet-stream` | `test_detect_mime_unknown` | Unit |
| Fresh Python env installation succeeds | `test_install_no_system_deps` | Integration |
| No libmagic test skips in CI | `test_examples_all_enabled` | Integration |
| Existing file operations work after upgrade | `test_backward_compatibility` | Integration |
| FileStore processes attachments correctly | `test_filestore_all_mime_types` | Integration |
| Corrupted file handled gracefully | `test_corrupted_file_handling` | Unit |
| Empty file handled gracefully | `test_empty_file_handling` | Unit |

### Test Tiers

**Unit Tests (new):**
```python
# tests/test_mime_detection.py
class TestMimeDetection:
    def test_detect_mime_pdf(self):
        """PDF file detected correctly via filetype"""
        pdf_content = b"%PDF-1.4..."  # Valid PDF header
        mime = detect_mime(pdf_content, "test.pdf")
        assert mime == "application/pdf"
    
    def test_detect_mime_png(self):
        """PNG image detected correctly"""
        png_content = b"\x89PNG\r\n\x1a\n..."  # Valid PNG header
        mime = detect_mime(png_content, "test.png")
        assert mime == "image/png"
    
    def test_detect_mime_jpeg(self):
        """JPEG image detected correctly"""
        jpeg_content = b"\xff\xd8\xff..."  # Valid JPEG header
        mime = detect_mime(jpeg_content, "test.jpg")
        assert mime == "image/jpeg"
    
    def test_detect_mime_text(self):
        """Text file detected correctly"""
        text_content = b"Hello, world!"
        mime = detect_mime(text_content, "test.txt")
        assert mime == "text/plain"
    
    def test_detect_mime_csv(self):
        """CSV file detected correctly"""
        csv_content = b"name,age\nAlice,30"
        mime = detect_mime(csv_content, "test.csv")
        assert mime in ["text/csv", "text/plain"]  # filetype may return text/plain
    
    def test_detect_mime_json(self):
        """JSON file detected correctly"""
        json_content = b'{"key": "value"}'
        mime = detect_mime(json_content, "test.json")
        assert mime in ["application/json", "text/plain"]  # filetype may return text/plain
    
    def test_detect_mime_unknown(self):
        """Unknown binary defaults to application/octet-stream"""
        unknown_content = b"\x00\x01\x02\x03\x04"
        mime = detect_mime(unknown_content, "test.bin")
        assert mime == "application/octet-stream"
    
    def test_detect_mime_empty(self):
        """Empty file handled gracefully"""
        empty_content = b""
        mime = detect_mime(empty_content, "test.txt")
        assert mime in ["text/plain", "application/octet-stream"]
    
    def test_detect_mime_fallback_to_extension(self):
        """Falls back to extension when content detection fails"""
        # Content that filetype can't identify
        ambiguous_content = b"Some text content"
        mime = detect_mime(ambiguous_content, "document.pdf")
        # Should fallback to extension-based detection
        assert mime == "application/pdf"
```

**Integration Tests (existing + updates):**
```python
# tests/test_examples.py - Enable all previously skipped tests
def test_storage_patterns():
    """Previously skipped due to libmagic - now should pass"""
    # Remove skip decorator
    ...

def test_quickstart():
    """Previously skipped due to libmagic - now should pass"""
    # Remove skip decorator
    ...

# 9 total tests to enable
```

**Contract Tests:**
```python
# packages/lye/tests/test_files.py
class TestFileReadContract:
    async def test_read_pdf(self):
        """PDF reading contract maintained"""
        result, files = await read_file(file_url="test.pdf")
        assert result["success"] == True
        assert result["type"] == "pdf"
        assert "text" in result or "processing_method" in result
    
    async def test_read_csv(self):
        """CSV reading contract maintained"""
        result, files = await read_file(file_url="test.csv")
        assert result["success"] == True
        assert "statistics" in result
        assert "preview" in result

# packages/narrator/tests/test_attachment.py
class TestAttachmentContract:
    async def test_from_file_path(self):
        """Attachment.from_file_path contract maintained"""
        attachment = Attachment.from_file_path("test.pdf")
        assert attachment.filename == "test.pdf"
        assert attachment.mime_type == "application/pdf"
        assert attachment.content is not None
```

### Negative & Edge Cases

**Edge Case Tests:**
1. ✅ Empty files
2. ✅ Corrupted files (invalid headers)
3. ✅ Files with mismatched extension and content (e.g., PDF with .txt extension)
4. ✅ Very small files (< 100 bytes)
5. ✅ Files at size limit boundary (exactly 50MB)
6. ✅ Files with no extension
7. ✅ Files with multiple extensions (e.g., `archive.tar.gz`)
8. ✅ Non-UTF8 text files

**Negative Case Tests:**
```python
def test_unsupported_mime_type():
    """Unsupported MIME type raises appropriate error"""
    # Executable file
    exe_content = b"MZ\x90\x00..."  # Windows EXE header
    with pytest.raises(UnsupportedFileTypeError):
        await file_store.validate_file(exe_content, "malware.exe")

def test_file_too_large():
    """Oversized file raises appropriate error"""
    large_content = b"x" * (51 * 1024 * 1024)  # 51MB
    with pytest.raises(FileTooLargeError):
        await file_store.validate_file(large_content, "huge.txt")
```

### Performance Tests

**Not required** but could add:
```python
def test_mime_detection_performance():
    """MIME detection completes within acceptable time"""
    large_file = b"x" * (10 * 1024 * 1024)  # 10MB
    import time
    start = time.time()
    mime = filetype.guess_mime(large_file)
    elapsed = time.time() - start
    assert elapsed < 0.1  # Should be nearly instant (only reads first 8KB)
```

### CI Requirements
- ✅ All tests run in CI (no skips)
- ✅ Tests block merge if failing
- ✅ Linting passes
- ✅ No dependency installation warnings
- ✅ Test coverage maintained or improved

## 11. Risks & Open Questions

### Known Risks & Mitigations

**Risk 1: MIME detection differences for edge cases**
- **Likelihood**: Medium
- **Impact**: Low (fallback strategy handles it)
- **Mitigation**: 
  - Comprehensive test suite covering all allowed MIME types
  - Two-tier fallback (filetype → mimetypes → default)
  - Monitor error rates after deployment

**Risk 2: Undiscovered file type edge cases**
- **Likelihood**: Low
- **Impact**: Low (graceful degradation)
- **Mitigation**:
  - Extensive testing with real-world file samples
  - Fallback to safe default (`application/octet-stream`)
  - Can always add custom detection logic for specific types if needed

**Risk 3: Test coverage gaps**
- **Likelihood**: Low
- **Impact**: Medium (bugs in production)
- **Mitigation**:
  - TDD approach ensures tests before implementation
  - Enable all 9 previously skipped integration tests
  - Manual testing with examples before deployment

**Risk 4: User confusion if MIME types change**
- **Likelihood**: Very Low
- **Impact**: Low
- **Mitigation**:
  - MIME types for common formats (PDF, PNG, JPEG) are standardized
  - Document any intentional changes in CHANGELOG
  - Most users don't directly interact with MIME types

### Open Questions

**Q1: Should we add a configuration option to prefer extension-based detection?**
- **Proposed answer**: No - content-based is more secure and reliable
- **Resolution**: Keep content-based as primary, extension as fallback

**Q2: Should we log when fallback to mimetypes occurs?**
- **Proposed answer**: Yes, at debug level for first release to monitor coverage
- **Resolution**: Add debug logging, can remove later if not useful

**Q3: Do we need a migration guide for users?**
- **Proposed answer**: No - internal change only, no user-facing impact
- **Resolution**: Mention in CHANGELOG as improvement, not breaking change

**Q4: Should we add explicit tests for all 18 allowed MIME types?**
- **Proposed answer**: Yes - comprehensive coverage ensures no regressions
- **Resolution**: Create test cases for each type in `DEFAULT_ALLOWED_MIME_TYPES`

## 12. Milestones / Plan (post‑approval)

### Task Breakdown

**Milestone 1: Setup & Tests (TDD)**
- [ ] **Task 1.1**: Add `filetype>=1.2.0` to all package dependencies
  - DoD: pyproject.toml files updated, uv.lock regenerated, `uv sync` succeeds
- [ ] **Task 1.2**: Write failing unit tests for MIME detection
  - DoD: Tests for all 18 allowed MIME types, all currently failing
- [ ] **Task 1.3**: Write failing edge case tests
  - DoD: Tests for empty files, corrupted files, mismatched extensions, all failing

**Milestone 2: Implementation**
- [ ] **Task 2.1**: Update `lye/files.py` MIME detection
  - DoD: Implementation complete, unit tests pass, linting passes
- [ ] **Task 2.2**: Update `narrator/storage/file_store.py` MIME detection
  - DoD: Implementation complete, unit tests pass, linting passes
- [ ] **Task 2.3**: Update `narrator/models/attachment.py` MIME detection (3 locations)
  - DoD: Implementation complete, unit tests pass, linting passes
- [ ] **Task 2.4**: Remove `import magic`, add `import filetype` and `import mimetypes`
  - DoD: No references to `magic` remain, all tests pass

**Milestone 3: Integration & Documentation**
- [ ] **Task 3.1**: Enable all skipped tests in `tests/test_examples.py`
  - DoD: All 9 previously skipped tests pass
- [ ] **Task 3.2**: Update documentation files (7 files)
  - DoD: All libmagic references removed, no broken links
- [ ] **Task 3.3**: Update CHANGELOG files
  - DoD: Changes documented in lye, narrator, tyler CHANGELOGs
- [ ] **Task 3.4**: Manual smoke testing
  - DoD: Run all examples, verify file operations work correctly

**Milestone 4: Validation & Merge**
- [ ] **Task 4.1**: Full test suite passes
  - DoD: `pytest` runs cleanly, no skipped tests (except pre-existing)
- [ ] **Task 4.2**: Linting passes
  - DoD: `ruff check`, `mypy` (if applicable) pass
- [ ] **Task 4.3**: Create implementation summary
  - DoD: `/directive/specs/remove-libmagic-dependency/implementation_summary.md` created
- [ ] **Task 4.4**: Final review and merge
  - DoD: PR approved, CI green, merged to main

### Dependencies
- No external dependencies or blockers
- Can be completed in single PR
- Estimated effort: 4-6 hours

### Owner
- AI Agent (with engineer approval at each gate)

---

**Approval Gate**: Do not start coding until this TDR is reviewed and approved.

