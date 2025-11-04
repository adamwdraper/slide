# Test Plan — Remove libmagic System Dependency

## Existing Test Coverage Analysis

### ✅ packages/lye/tests/test_files.py (25 tests)
**Current coverage:**
- Text file reading (lines 76-89)
- JSON file reading and path extraction (lines 92-127)
- CSV file reading (lines 130-146)
- PDF file reading (lines 149-182, 199-229)
- File writing (text, JSON, CSV, binary) (lines 258-350)
- Error handling (encoding failures, parse errors) (lines 232-255, 376-420)
- Unknown MIME types (lines 423-437)

**MIME detection usage:** All tests mock `magic.from_buffer` → Need to update to test `filetype.guess_mime()`

### ✅ packages/narrator/tests/test_file_store.py (20 tests)
**Current coverage:**
- File size limit enforcement (lines 185-199)
- Storage size limit enforcement (lines 202-216)
- **MIME type validation** (lines 219-233) ⚠️ Critical for our change
- **Automatic MIME detection** (lines 357-367) ⚠️ Critical for our change
- Save/get/delete operations (lines 136-180)
- Batch operations (lines 260-283)

**MIME detection usage:** Test at line 357 directly tests MIME detection

### ✅ packages/narrator/tests/test_attachment.py (30 tests)
**Current coverage:**
- Attachment creation and serialization (lines 34-83)
- Content handling (bytes, base64, strings) (lines 86-128)
- **MIME type detection** (lines 379-396) ⚠️ Critical for our change
- **from_file_path()** creation (lines 365-377) ⚠️ Critical for our change
- Storage integration (lines 131-154, 286-309)
- Error handling (lines 270-283)

**MIME detection usage:** Tests at lines 365, 379 use MIME detection

---

## New Tests Required

### 1. Core MIME Detection Test Suite (NEW FILE)
**Location:** `packages/lye/tests/test_mime_detection.py`

```python
"""Comprehensive MIME type detection tests for filetype library"""

class TestMimeDetection:
    """Test MIME detection for all supported file types"""
    
    # Documents (5 tests)
    def test_detect_pdf(self):
        """PDF files detected as application/pdf"""
        pdf_content = b"%PDF-1.4\n%..."  # Valid PDF header
        
    def test_detect_docx(self):
        """DOCX files detected correctly"""
        # PK zip signature for Office files
        
    def test_detect_text(self):
        """Plain text files detected as text/plain"""
        
    def test_detect_csv(self):
        """CSV files detected (may be text/csv or text/plain)"""
        
    def test_detect_json(self):
        """JSON files detected (may be application/json or text/plain)"""
    
    # Images (5 tests)
    def test_detect_jpeg(self):
        """JPEG images detected as image/jpeg"""
        jpeg_content = b"\xff\xd8\xff..."  # JPEG magic bytes
        
    def test_detect_png(self):
        """PNG images detected as image/png"""
        png_content = b"\x89PNG\r\n\x1a\n..."  # PNG signature
        
    def test_detect_gif(self):
        """GIF images detected as image/gif"""
        gif_content = b"GIF89a..."  # GIF signature
        
    def test_detect_webp(self):
        """WebP images detected as image/webp"""
        webp_content = b"RIFF....WEBP"  # WebP signature
        
    def test_detect_svg(self):
        """SVG files detected as image/svg+xml"""
        svg_content = b"<?xml version..."  # SVG header
    
    # Audio (6 tests)
    def test_detect_mp3(self):
        """MP3 files detected as audio/mpeg"""
        mp3_content = b"ID3" or b"\xff\xfb"  # MP3 signatures
        
    def test_detect_wav(self):
        """WAV files detected as audio/wav"""
        wav_content = b"RIFF....WAVE"  # WAV signature
        
    def test_detect_ogg(self):
        """OGG files detected as audio/ogg"""
        ogg_content = b"OggS"  # OGG signature
        
    def test_detect_m4a(self):
        """M4A files detected as audio/x-m4a"""
        
    def test_detect_flac(self):
        """FLAC files detected as audio/flac"""
        flac_content = b"fLaC"  # FLAC signature
        
    def test_detect_aac(self):
        """AAC files detected as audio/aac"""
    
    # Archives (3 tests)
    def test_detect_zip(self):
        """ZIP files detected as application/zip"""
        zip_content = b"PK\x03\x04"  # ZIP signature
        
    def test_detect_tar(self):
        """TAR files detected as application/x-tar"""
        
    def test_detect_gzip(self):
        """GZIP files detected as application/gzip"""
        gzip_content = b"\x1f\x8b"  # GZIP signature
    
    # Edge Cases (8 tests)
    def test_detect_empty_file(self):
        """Empty files handled gracefully"""
        empty_content = b""
        # Should fallback to mimetypes or return application/octet-stream
        
    def test_detect_very_small_file(self):
        """Files < 100 bytes detected correctly"""
        small_content = b"small"
        
    def test_detect_corrupted_header(self):
        """Corrupted file headers handled gracefully"""
        corrupted = b"%PDF-CORRUPTED"
        # Should fallback to extension-based detection
        
    def test_detect_mismatched_extension(self):
        """Files with wrong extension use content detection"""
        # PDF content with .txt extension
        pdf_as_txt = (b"%PDF-1.4...", "document.txt")
        # Should detect as PDF from content, not extension
        
    def test_detect_no_extension(self):
        """Files without extension detected from content"""
        content = b"%PDF-1.4..."
        filename = "document"  # No extension
        # Should detect as PDF
        
    def test_detect_unknown_binary(self):
        """Unknown binary content defaults to application/octet-stream"""
        unknown = b"\x00\x01\x02\x03\x04\x05"
        
    def test_fallback_to_mimetypes(self):
        """Falls back to extension when content detection fails"""
        ambiguous_content = b"Some text that could be anything"
        filename = "document.pdf"
        # filetype returns None → should use mimetypes.guess_type()
        
    def test_text_file_with_special_encoding(self):
        """Text files with non-UTF8 encoding handled"""
        latin1_content = b"Caf\xe9"  # Latin-1 encoded
```

**Estimated:** 27 new unit tests

---

### 2. Update Existing Tests (3 files to modify)

#### packages/lye/tests/test_files.py
**Changes needed:**
- Remove all `patch('magic.from_buffer')` mocks (9 locations)
- Update to test actual `filetype.guess_mime()` behavior
- Add assertions for fallback behavior

**Specific updates:**
```python
# BEFORE (line 80)
patch('magic.from_buffer', return_value='text/plain')

# AFTER (no mock needed - test real behavior)
# filetype.guess_mime() will be called directly
```

**Tests to update:** 9 tests need mock removal

#### packages/narrator/tests/test_file_store.py
**Changes needed:**
- Line 357-367: Update MIME detection test to verify filetype behavior
- Add test for fallback logic
- Add test for all 18 allowed MIME types

**New tests to add:**
```python
@pytest.mark.asyncio
async def test_all_allowed_mime_types(temp_store: FileStore):
    """Verify all allowed MIME types can be detected and stored"""
    test_files = {
        'application/pdf': b'%PDF-1.4',
        'image/jpeg': b'\xff\xd8\xff\xe0',
        'image/png': b'\x89PNG\r\n\x1a\n',
        'text/plain': b'Hello World',
        # ... all 18 types
    }
    
    for mime_type, content in test_files.items():
        # Generate appropriate filename
        ext = mime_type.split('/')[-1]
        filename = f"test.{ext}"
        
        # Should save and detect correctly
        result = await temp_store.save(content, filename)
        assert result['mime_type'] == mime_type

@pytest.mark.asyncio  
async def test_mime_fallback_to_extension(temp_store: FileStore):
    """Test fallback to extension-based detection"""
    # Content that filetype can't identify
    ambiguous = b"Some plain text content"
    # But filename has clear extension
    result = await temp_store.save(ambiguous, "document.pdf")
    # Should use extension as fallback
    assert result['mime_type'] == 'application/pdf'
```

**Tests to update:** 2 existing + 2 new = 4 tests

#### packages/narrator/tests/test_attachment.py
**Changes needed:**
- Lines 365-377: `from_file_path()` test - verify MIME detection works
- Lines 379-396: `detect_mime_type()` test - update for filetype behavior

**New tests to add:**
```python
@pytest.mark.asyncio
async def test_attachment_mime_fallback():
    """Test MIME detection with fallback"""
    # Ambiguous content
    content = b"Some content"
    attachment = Attachment(
        filename="test.pdf",  # Clear extension
        content=content
    )
    attachment.detect_mime_type()
    # Should use fallback to extension
    assert attachment.mime_type == "application/pdf"

def test_attachment_from_file_path_mime_detection(temp_file):
    """Test from_file_path detects MIME correctly"""
    # Create various file types and verify detection
    # This ensures the full integration works
```

**Tests to update:** 2 existing + 2 new = 4 tests

---

### 3. Integration Tests (UPDATE EXISTING)

#### tests/test_examples.py
**Changes needed:**
- **Remove 9 test skips** (lines 35-48)
- Verify all examples run without libmagic

**Before:**
```python
EXAMPLES_TO_SKIP = [
    "integrations/storage-patterns.py",  # Requires libmagic
    "use-cases/slack-bot/basic.py",  # Requires libmagic
    # ... 7 more
]
```

**After:**
```python
EXAMPLES_TO_SKIP = [
    # libmagic dependency removed - all examples should work
]
```

**Tests affected:** 9 integration tests

---

### 4. Real File Sample Tests (NEW)

**Location:** `packages/lye/tests/test_real_files.py`

```python
"""Tests with actual file samples to ensure real-world compatibility"""

@pytest.fixture
def sample_files_dir():
    """Create directory with real file samples"""
    # Generate small valid files for each type
    
class TestRealFileSamples:
    """Test MIME detection with real file samples"""
    
    def test_real_pdf_detection(self, sample_files_dir):
        """Real PDF file detected correctly"""
        # Use pypdf to generate minimal valid PDF
        
    def test_real_image_detection(self, sample_files_dir):
        """Real image files detected correctly"""
        # Use PIL to generate small PNG, JPEG
        
    def test_real_audio_detection(self, sample_files_dir):
        """Real audio files detected correctly"""
        # Use small audio file samples
```

**Estimated:** 5-10 tests with real file samples

---

## Test Execution Strategy

### Phase 1: Write Failing Tests (TDD)
1. Create `test_mime_detection.py` with all 27 tests
2. Run tests with `python-magic` still in place - **should pass**
3. Remove `python-magic`, don't add `filetype` yet - **should fail**

### Phase 2: Implement Changes
4. Add `filetype` dependency
5. Update MIME detection code in 3 files
6. Run tests - **should pass**

### Phase 3: Update Existing Tests  
7. Remove `magic.from_buffer` mocks from `test_files.py`
8. Update `test_file_store.py` with fallback tests
9. Update `test_attachment.py` with new assertions
10. Run full test suite - **should pass**

### Phase 4: Integration Verification
11. Enable all 9 skipped tests in `test_examples.py`
12. Run examples manually
13. Run full integration test suite - **should pass**

---

## Test Coverage Goals

| Category | Current | Target | New Tests |
|----------|---------|--------|-----------|
| MIME detection unit tests | 0 | 27 | +27 |
| File store MIME tests | 2 | 6 | +4 |
| Attachment MIME tests | 2 | 6 | +4 |
| Integration tests (enabled) | 0 | 9 | +9 (remove skips) |
| Real file sample tests | 0 | 8 | +8 |
| **Total** | **~75** | **~125** | **+52** |

---

## Success Criteria

✅ All 27 MIME type detection tests pass  
✅ All 18 allowed MIME types can be detected  
✅ Fallback to `mimetypes` works correctly  
✅ Edge cases (empty, corrupted, mismatched) handled  
✅ All existing tests pass without `magic.from_buffer` mocks  
✅ All 9 previously skipped integration tests pass  
✅ No test failures in CI  
✅ Test coverage maintains >80% for affected files  

---

## File Samples for Testing

We'll need small valid file samples for:

**Critical (must have):**
- ✅ PDF (minimal valid PDF)
- ✅ PNG (1x1 pixel)
- ✅ JPEG (1x1 pixel)  
- ✅ MP3 (1 second silence)
- ✅ JSON ({"test": true})
- ✅ CSV (header + 1 row)
- ✅ ZIP (empty archive)

**Nice to have:**
- GIF, WebP, WAV, OGG, TAR, GZIP

These can be generated programmatically in test fixtures.

