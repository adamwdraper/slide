# Spec (per PR)

**Feature name**: Remove libmagic System Dependency  
**One-line summary**: Replace python-magic with filetype for pure-Python MIME type detection, eliminating the libmagic1 system dependency requirement.

---

## Problem

The Slide framework currently requires users to install the `libmagic1` system library (`python-magic` package) for MIME type detection from file content. This creates significant friction:

1. **Installation complexity**: Users must install system packages separately before using Slide
   - macOS: `brew install libmagic`
   - Ubuntu: `sudo apt-get install libmagic1`
   - Other systems: Various package managers or manual compilation
   
2. **Development friction**: Multiple test files are skipped due to libmagic dependency issues (see `tests/test_examples.py` lines 35-48)

3. **Deployment complexity**: Production environments require system-level package installation, complicating containerization and deployment

4. **Cross-platform inconsistencies**: Different platforms may have different libmagic versions or behaviors

This is a foundational dependency issue that affects all users across the `lye`, `narrator`, and `tyler` packages.

## Goal

Slide framework should use pure-Python MIME type detection that requires no system dependencies, making installation as simple as `pip install` or `uv add`.

## Success Criteria
- [x] Users can install and use Slide packages without installing any system dependencies
- [x] All previously skipped tests in `tests/test_examples.py` pass without libmagic
- [x] MIME type detection works accurately for all currently supported file types
- [x] Documentation no longer mentions libmagic installation requirements

## User Story

As a **Slide framework user**, I want **to install and use file processing capabilities with just pip/uv**, so that **I don't have to manage system-level dependencies or deal with platform-specific installation issues**.

## Flow / States

**Happy Path:**
1. User runs `pip install slide-tyler` (or uv equivalent)
2. User creates an agent with file tools from `lye`
3. User uploads/processes files (PDFs, images, text, etc.)
4. MIME types are correctly detected using pure-Python detection
5. Files are processed without any system dependency errors

**Edge Case - Unknown File Type:**
1. User uploads a file with uncommon/custom extension
2. `filetype` attempts content-based detection
3. Falls back to `mimetypes.guess_type()` if needed
4. Returns `application/octet-stream` as safe default if detection fails
5. File is still processed/stored successfully

## UX Links

No UI changes - this is an internal implementation improvement.

- Related Documentation: 
  - `docs/guides/your-first-agent.mdx` (line 435)
  - `docs/standalone-packages/using-lye.mdx` (line 32)
  - `packages/lye/README.md` (lines 90-93)
  - `packages/narrator/README.md` (line 504)
  - `examples/DEVELOPMENT.md` (lines 192-203)

## Requirements

**Must:**
- Replace all `import magic` statements with `import filetype`
- Maintain identical MIME type detection accuracy for all currently supported file types
- Update all package dependencies (`pyproject.toml` files) to replace `python-magic` with `filetype`
- Remove all libmagic installation instructions from documentation
- Ensure backward compatibility - no breaking API changes
- Pass all existing tests

**Must not:**
- Change any public APIs or function signatures
- Reduce the set of supported file types
- Introduce any new system dependencies
- Break existing user code that relies on file processing

## Acceptance Criteria

**File Detection:**
- Given a PDF file, when `read_file()` is called, then MIME type is correctly detected as `application/pdf` without libmagic
- Given a PNG image, when `Attachment.from_file_path()` is called, then MIME type is correctly detected as `image/png`
- Given a text file, when file validation occurs, then MIME type is correctly detected as `text/plain`
- Given an unknown binary file, when MIME detection runs, then it returns `application/octet-stream` without errors

**Package Installation:**
- Given a fresh Python environment, when running `pip install slide-tyler`, then installation completes without requiring system packages
- Given a CI environment, when tests run, then no libmagic-related test skips occur

**Backward Compatibility:**
- Given existing user code using file tools, when upgrading to new version, then all file operations continue working identically
- Given the narrator FileStore, when processing attachments, then all file types are stored and retrieved correctly

**Documentation:**
- Given the README files, when users read installation instructions, then no mention of libmagic appears
- Given troubleshooting docs, when users encounter errors, then no libmagic-related error documentation exists

**Negative Cases:**
- Given a corrupted file, when MIME detection runs, then it handles errors gracefully without crashes
- Given an empty file, when processing occurs, then appropriate error handling occurs without libmagic-specific errors

## Non-Goals

- Adding support for additional file types beyond current capabilities
- Performance optimization of MIME detection (though filetype should be comparable)
- Adding file validation beyond MIME type detection
- Changing the file storage architecture or processing pipelines
- Supporting files larger than current size limits

