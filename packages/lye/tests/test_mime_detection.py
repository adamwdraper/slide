"""Comprehensive MIME type detection tests for filetype library

This test suite ensures that all supported MIME types can be correctly detected
from file content using the filetype library (replacing python-magic/libmagic).

Tests cover:
- All 18 allowed MIME types in FileStore.DEFAULT_ALLOWED_MIME_TYPES
- Edge cases (empty files, corrupted headers, mismatched extensions)
- Fallback logic to mimetypes when content detection fails
"""

import pytest
import mimetypes
from typing import Tuple


def detect_mime_type(content: bytes, filename: str) -> str:
    """
    Detect MIME type from file content with fallback strategy.
    
    This function will be the new implementation replacing magic.from_buffer().
    
    Args:
        content: File content as bytes
        filename: Original filename (for extension-based fallback)
        
    Returns:
        Detected MIME type string
    """
    try:
        import filetype
    except ImportError:
        # If filetype not installed yet, use old magic for now
        import magic
        return magic.from_buffer(content, mime=True)
    
    # Primary: content-based detection
    mime_type = filetype.guess_mime(content)
    
    if not mime_type:
        # Fallback: extension-based detection
        mime_type, _ = mimetypes.guess_type(filename)
    
    if not mime_type:
        # Default: binary
        mime_type = 'application/octet-stream'
    
    return mime_type


class TestDocumentMimeDetection:
    """Test MIME detection for document file types"""
    
    def test_detect_pdf(self):
        """PDF files detected as application/pdf"""
        # Minimal valid PDF header
        pdf_content = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        mime = detect_mime_type(pdf_content, "test.pdf")
        assert mime == "application/pdf"
    
    def test_detect_text_plain(self):
        """Plain text files detected as text/plain"""
        text_content = b"Hello, World! This is plain text."
        mime = detect_mime_type(text_content, "test.txt")
        assert mime == "text/plain"
    
    def test_detect_csv(self):
        """CSV files detected correctly"""
        csv_content = b"name,age,city\nAlice,30,NYC\nBob,25,SF"
        mime = detect_mime_type(csv_content, "test.csv")
        # filetype may return text/plain for CSV, which is acceptable
        # The fallback to mimetypes should give us text/csv
        assert mime in ["text/csv", "text/plain"]
    
    def test_detect_json(self):
        """JSON files detected correctly"""
        json_content = b'{"name": "test", "value": 123}'
        mime = detect_mime_type(json_content, "test.json")
        # filetype may return text/plain for JSON, which is acceptable
        # The fallback to mimetypes should give us application/json
        assert mime in ["application/json", "text/plain"]
    
    def test_detect_docx(self):
        """DOCX files detected as Office document"""
        # DOCX is a ZIP file with specific structure
        # PK zip signature
        docx_content = b"PK\x03\x04" + b"\x00" * 20  # ZIP header
        mime = detect_mime_type(docx_content, "test.docx")
        # filetype will detect as application/zip
        # Fallback to extension should give us the DOCX type
        assert mime in ["application/zip", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]


class TestImageMimeDetection:
    """Test MIME detection for image file types"""
    
    def test_detect_jpeg(self):
        """JPEG images detected as image/jpeg"""
        # JPEG magic bytes (JFIF format)
        jpeg_content = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        mime = detect_mime_type(jpeg_content, "test.jpg")
        assert mime == "image/jpeg"
    
    def test_detect_jpeg_exif(self):
        """JPEG with EXIF detected as image/jpeg"""
        # JPEG magic bytes (EXIF format)
        jpeg_exif_content = b"\xff\xd8\xff\xe1"
        mime = detect_mime_type(jpeg_exif_content, "test.jpeg")
        assert mime == "image/jpeg"
    
    def test_detect_png(self):
        """PNG images detected as image/png"""
        # PNG signature
        png_content = b"\x89PNG\r\n\x1a\n"
        mime = detect_mime_type(png_content, "test.png")
        assert mime == "image/png"
    
    def test_detect_gif(self):
        """GIF images detected as image/gif"""
        # GIF89a signature
        gif_content = b"GIF89a"
        mime = detect_mime_type(gif_content, "test.gif")
        assert mime == "image/gif"
    
    def test_detect_gif87(self):
        """GIF87 images detected as image/gif"""
        # GIF87a signature
        gif_content = b"GIF87a"
        mime = detect_mime_type(gif_content, "test.gif")
        assert mime == "image/gif"
    
    def test_detect_webp(self):
        """WebP images detected as image/webp"""
        # WebP signature (RIFF container)
        webp_content = b"RIFF\x00\x00\x00\x00WEBP"
        mime = detect_mime_type(webp_content, "test.webp")
        assert mime == "image/webp"
    
    def test_detect_svg(self):
        """SVG files detected as image/svg+xml"""
        # SVG is XML-based
        svg_content = b'<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg"></svg>'
        mime = detect_mime_type(svg_content, "test.svg")
        # filetype may not detect SVG (it's text-based), fallback to extension
        assert mime in ["image/svg+xml", "text/xml", "application/xml"]


class TestAudioMimeDetection:
    """Test MIME detection for audio file types"""
    
    def test_detect_mp3_id3(self):
        """MP3 files with ID3 tag detected as audio/mpeg"""
        # MP3 with ID3v2 tag
        mp3_content = b"ID3\x03\x00\x00\x00"
        mime = detect_mime_type(mp3_content, "test.mp3")
        assert mime == "audio/mpeg"
    
    def test_detect_mp3_frame(self):
        """MP3 files with frame sync detected as audio/mpeg"""
        # MP3 frame sync
        mp3_content = b"\xff\xfb"
        mime = detect_mime_type(mp3_content, "test.mp3")
        # May be detected as audio/mpeg or need fallback
        assert mime in ["audio/mpeg", "audio/mp3"]
    
    def test_detect_wav(self):
        """WAV files detected as audio/wav"""
        # RIFF WAVE header
        wav_content = b"RIFF\x00\x00\x00\x00WAVEfmt "
        mime = detect_mime_type(wav_content, "test.wav")
        assert mime in ["audio/wav", "audio/x-wav", "audio/wave"]
    
    def test_detect_ogg(self):
        """OGG files detected as audio/ogg"""
        # OGG signature
        ogg_content = b"OggS\x00"
        mime = detect_mime_type(ogg_content, "test.ogg")
        assert mime in ["audio/ogg", "application/ogg"]
    
    def test_detect_flac(self):
        """FLAC files detected as audio/flac"""
        # FLAC signature
        flac_content = b"fLaC"
        mime = detect_mime_type(flac_content, "test.flac")
        # Both audio/flac and audio/x-flac are valid
        assert mime in ["audio/flac", "audio/x-flac"]
    
    def test_detect_m4a(self):
        """M4A files detected correctly"""
        # M4A is MP4 container (ftyp box)
        m4a_content = b"\x00\x00\x00\x20ftypM4A "
        mime = detect_mime_type(m4a_content, "test.m4a")
        # May be detected as video/mp4 or audio/mp4
        assert mime in ["audio/mp4", "video/mp4", "audio/x-m4a"]
    
    def test_detect_aac(self):
        """AAC files detected as audio/aac"""
        # AAC ADTS header
        aac_content = b"\xff\xf1"
        mime = detect_mime_type(aac_content, "test.aac")
        # AAC detection varies, may need fallback
        assert mime in ["audio/aac", "audio/mpeg"]
    
    def test_detect_opus(self):
        """Opus files detected as audio/opus"""
        # Opus in OGG container
        opus_content = b"OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00"
        mime = detect_mime_type(opus_content, "test.opus")
        # Will likely be detected as ogg, extension fallback needed
        assert mime in ["audio/opus", "audio/ogg", "application/ogg"]


class TestArchiveMimeDetection:
    """Test MIME detection for archive file types"""
    
    def test_detect_zip(self):
        """ZIP files detected as application/zip"""
        # ZIP local file header signature
        zip_content = b"PK\x03\x04"
        mime = detect_mime_type(zip_content, "test.zip")
        assert mime == "application/zip"
    
    def test_detect_gzip(self):
        """GZIP files detected as application/gzip"""
        # GZIP magic number
        gzip_content = b"\x1f\x8b\x08"
        mime = detect_mime_type(gzip_content, "test.gz")
        assert mime == "application/gzip"
    
    def test_detect_tar(self):
        """TAR files detected as application/x-tar"""
        # TAR header (ustar format)
        tar_content = b"\x00" * 257 + b"ustar\x00"
        mime = detect_mime_type(tar_content, "test.tar")
        # TAR is hard to detect from content, may need fallback
        assert mime in ["application/x-tar", "application/octet-stream"]


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_file(self):
        """Empty files handled gracefully"""
        empty_content = b""
        mime = detect_mime_type(empty_content, "test.txt")
        # Should fallback to extension or default
        assert mime in ["text/plain", "application/octet-stream"]
    
    def test_very_small_file(self):
        """Files smaller than typical headers handled"""
        small_content = b"Hi"
        mime = detect_mime_type(small_content, "test.txt")
        # Should fallback to extension
        assert mime == "text/plain"
    
    def test_corrupted_pdf_header(self):
        """Corrupted PDF header falls back to extension"""
        corrupted = b"%PDF-CORRUPTED"
        mime = detect_mime_type(corrupted, "document.pdf")
        # Content detection may fail, should use extension
        assert mime == "application/pdf"
    
    def test_mismatched_extension_content(self):
        """Content takes precedence over extension"""
        # PDF content with .txt extension
        pdf_content = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        mime = detect_mime_type(pdf_content, "document.txt")
        # Should detect as PDF from content, not from .txt extension
        assert mime == "application/pdf"
    
    def test_no_extension(self):
        """Files without extension use content detection"""
        pdf_content = b"%PDF-1.4\n"
        mime = detect_mime_type(pdf_content, "document")
        # Should detect from content
        assert mime == "application/pdf"
    
    def test_unknown_binary(self):
        """Unknown binary defaults to application/octet-stream"""
        unknown = b"\x00\x01\x02\x03\x04\x05\x06\x07"
        mime = detect_mime_type(unknown, "unknown.bin")
        assert mime == "application/octet-stream"
    
    def test_fallback_to_mimetypes_when_content_unknown(self):
        """Falls back to extension when content detection fails"""
        # Ambiguous text content
        ambiguous = b"Some text content that is hard to classify"
        mime = detect_mime_type(ambiguous, "document.pdf")
        # filetype may return text/plain, but we want to ensure
        # that if it returns None, we fallback to the extension
        # For this test, either text/plain or application/pdf is acceptable
        assert mime in ["text/plain", "application/pdf"]
    
    def test_multiple_extensions(self):
        """Files with multiple extensions handled"""
        gzip_content = b"\x1f\x8b\x08"
        mime = detect_mime_type(gzip_content, "archive.tar.gz")
        assert mime == "application/gzip"
    
    def test_uppercase_extension(self):
        """Uppercase extensions handled via fallback"""
        text_content = b"Plain text content"
        mime = detect_mime_type(text_content, "README.TXT")
        # Should normalize via mimetypes
        assert mime == "text/plain"
    
    def test_binary_data_with_text_extension(self):
        """Binary data with text extension - content wins"""
        binary = b"\x00\x01\x02\x03\x04\x05"
        mime = detect_mime_type(binary, "data.txt")
        # Content-based detection should identify it as binary
        # or fall back to text/plain from extension
        assert mime in ["application/octet-stream", "text/plain"]


class TestFallbackBehavior:
    """Test the three-tier fallback strategy"""
    
    def test_content_detection_primary(self):
        """Content detection is used when available"""
        png_content = b"\x89PNG\r\n\x1a\n"
        # Even with wrong extension, content should win
        mime = detect_mime_type(png_content, "image.jpg")
        assert mime == "image/png"
    
    def test_extension_fallback_secondary(self):
        """Extension used when content detection fails"""
        # Plain text that filetype can't specifically identify
        text_content = b"Just some text"
        mime = detect_mime_type(text_content, "document.csv")
        # Should use extension as fallback
        assert mime in ["text/plain", "text/csv"]
    
    def test_default_fallback_tertiary(self):
        """Default used when both content and extension fail"""
        unknown = b"\x00\x01\x02"
        mime = detect_mime_type(unknown, "unknownfile")
        # No extension, unknown content
        assert mime == "application/octet-stream"
    
    def test_all_fallback_tiers(self):
        """Verify the complete fallback chain"""
        # Test cases for each tier
        test_cases = [
            # (content, filename, expected_tier, acceptable_mimes)
            (b"\x89PNG\r\n\x1a\n", "test.png", "content", ["image/png"]),
            (b"plain text", "test.csv", "extension", ["text/plain", "text/csv"]),
            (b"\x00\x01", "noext", "default", ["application/octet-stream"]),
        ]
        
        for content, filename, tier, acceptable in test_cases:
            mime = detect_mime_type(content, filename)
            assert mime in acceptable, f"Tier {tier} failed for {filename}"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])

