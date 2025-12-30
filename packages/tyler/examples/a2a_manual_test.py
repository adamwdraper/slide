#!/usr/bin/env python3
"""Manual test script for A2A v0.3.0 type conversions.

Run with:
    cd packages/tyler && uv run python examples/a2a_manual_test.py
"""

import asyncio
from dotenv import load_dotenv
load_dotenv()

def test_type_conversions():
    """Test the A2A SDK type conversions work correctly."""
    print("\n" + "="*60)
    print("A2A v0.3.0 Type Conversion Tests")
    print("="*60)
    
    from tyler.a2a.types import (
        TextPart, FilePart, DataPart, Artifact,
        to_a2a_part, from_a2a_part, to_a2a_artifact
    )
    
    # Test 1: TextPart
    print("\n📝 Test 1: TextPart Conversion")
    text = TextPart(text="Hello from Tyler!")
    a2a_text = to_a2a_part(text)
    print(f"   Tyler TextPart: {text}")
    print(f"   A2A SDK TextPart: kind={a2a_text.kind}, text={a2a_text.text}")
    text_back = from_a2a_part(a2a_text)
    print(f"   Round-trip: {text_back}")
    assert text_back.text == text.text, "TextPart round-trip failed!"
    print("   ✅ PASSED")
    
    # Test 2: FilePart with bytes (inline file)
    print("\n📄 Test 2: FilePart (inline bytes) Conversion")
    file_content = b"This is test file content"
    file = FilePart(
        name="test.txt",
        media_type="text/plain",
        file_with_bytes=file_content
    )
    a2a_file = to_a2a_part(file)
    print(f"   Tyler FilePart: name={file.name}, size={len(file.file_with_bytes)} bytes")
    print(f"   A2A SDK FilePart: kind={a2a_file.kind}")
    print(f"   A2A SDK file object: {type(a2a_file.file).__name__}")
    print(f"   A2A SDK file.bytes (base64): {a2a_file.file.bytes[:20]}...")
    print(f"   A2A SDK file.mime_type: {a2a_file.file.mime_type}")
    print(f"   A2A SDK file.name: {a2a_file.file.name}")
    file_back = from_a2a_part(a2a_file)
    print(f"   Round-trip: name={file_back.name}, size={len(file_back.file_with_bytes)} bytes")
    assert file_back.file_with_bytes == file_content, "FilePart bytes round-trip failed!"
    print("   ✅ PASSED")
    
    # Test 3: FilePart with URI (remote file)
    print("\n🔗 Test 3: FilePart (URI) Conversion")
    file_uri = FilePart(
        name="remote.pdf",
        media_type="application/pdf",
        file_with_uri="https://example.com/docs/report.pdf"
    )
    a2a_file_uri = to_a2a_part(file_uri)
    print(f"   Tyler FilePart: name={file_uri.name}, uri={file_uri.file_with_uri}")
    print(f"   A2A SDK file object: {type(a2a_file_uri.file).__name__}")
    print(f"   A2A SDK file.uri: {a2a_file_uri.file.uri}")
    file_uri_back = from_a2a_part(a2a_file_uri)
    print(f"   Round-trip: uri={file_uri_back.file_with_uri}")
    assert file_uri_back.file_with_uri == file_uri.file_with_uri, "FilePart URI round-trip failed!"
    print("   ✅ PASSED")
    
    # Test 4: DataPart
    print("\n📊 Test 4: DataPart Conversion")
    data = DataPart(data={
        "metrics": {"accuracy": 0.95, "latency_ms": 42},
        "status": "completed",
        "tags": ["ml", "production"]
    })
    a2a_data = to_a2a_part(data)
    print(f"   Tyler DataPart: {data.data}")
    print(f"   A2A SDK DataPart: kind={a2a_data.kind}, data={a2a_data.data}")
    data_back = from_a2a_part(a2a_data)
    print(f"   Round-trip: {data_back.data}")
    assert data_back.data == data.data, "DataPart round-trip failed!"
    print("   ✅ PASSED")
    
    # Test 5: Artifact
    print("\n🎁 Test 5: Artifact Conversion")
    artifact = Artifact.create(
        name="Research Report",
        parts=[
            TextPart(text="# Research Findings\n\nThis is the summary..."),
            file,
            data
        ],
        description="Generated research report with data",
        metadata={"generated_by": "tyler", "version": "1.0"}
    )
    a2a_artifact = to_a2a_artifact(artifact)
    print(f"   Tyler Artifact: id={artifact.artifact_id[:8]}..., name={artifact.name}")
    print(f"   A2A SDK Artifact: id={a2a_artifact.artifact_id[:8]}..., name={a2a_artifact.name}")
    print(f"   A2A SDK parts count: {len(a2a_artifact.parts)}")
    print(f"   A2A SDK description: {a2a_artifact.description}")
    print("   ✅ PASSED")
    
    print("\n" + "="*60)
    print("✅ All A2A v0.3.0 type conversion tests passed!")
    print("="*60)


async def test_server_client():
    """Test server/client interaction (requires running server)."""
    print("\n" + "="*60)
    print("A2A Server/Client Test")
    print("="*60)
    
    try:
        from tyler.a2a import A2AAdapter
        
        adapter = A2AAdapter()
        
        # Try to connect to a running server
        print("\n🔌 Attempting to connect to http://localhost:8000...")
        connected = await adapter.connect("test_agent", "http://localhost:8000")
        
        if connected:
            print("   ✅ Connected successfully!")
            
            # Get agent card
            info = adapter.get_connection_info("test_agent")
            if info:
                print(f"   Agent: {info.get('name', 'Unknown')}")
                print(f"   Version: {info.get('version', 'Unknown')}")
            
            # Get available tools
            tools = adapter.get_tools_for_agent(["test_agent"])
            print(f"   Available delegation tools: {len(tools)}")
            for tool in tools:
                print(f"      - {tool.name}")
            
            await adapter.disconnect_all()
            print("   ✅ Disconnected")
        else:
            print("   ⚠️  Could not connect. Start the server first:")
            print("      uv run python examples/401_a2a_basic_server.py")
            
    except ImportError:
        print("   ⚠️  a2a-sdk not available")
    except Exception as e:
        print(f"   ⚠️  Connection failed: {e}")
        print("   Start the server first:")
        print("      uv run python examples/401_a2a_basic_server.py")


async def main():
    print("\n🧪 A2A v0.3.0 Manual Test Suite")
    print("   Testing SDK compliance and type conversions")
    
    # Always run type conversion tests
    test_type_conversions()
    
    # Try server/client test
    await test_server_client()
    
    print("\n✨ Testing complete!\n")


if __name__ == "__main__":
    asyncio.run(main())

