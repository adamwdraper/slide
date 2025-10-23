#!/usr/bin/env python3
"""Test all MCP transport types to find what works with Mintlify.

Tries: SSE, WebSocket, and Streamable HTTP (the likely winner!)
"""
import asyncio
from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client

try:
    from mcp.client.websocket import websocket_client
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    print("Note: WebSocket client not available (install websockets package)")


async def test_transport(transport_name: str, client_context_manager, url: str):
    """Test a specific transport type."""
    print(f"\n{'='*70}")
    print(f"Testing: {transport_name}")
    print(f"{'='*70}")
    print(f"URL: {url}")
    
    try:
        async with AsyncExitStack() as stack:
            # Connect
            print(f"   Connecting via {transport_name}...")
            result = await stack.enter_async_context(client_context_manager)
            
            # Handle different return types (2-tuple vs 3-tuple)
            if len(result) == 3:
                read_stream, write_stream, get_session_id = result
            else:
                read_stream, write_stream = result
            
            print(f"   ✓ Transport connected")
            
            # Create session
            session = await stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            print(f"   ✓ Session created")
            
            # Initialize
            init_result = await session.initialize()
            print(f"   ✓ Initialized!")
            print(f"   Server: {init_result.serverInfo.name if init_result.serverInfo else 'Unknown'}")
            
            # List tools
            tools_response = await session.list_tools()
            print(f"   ✓ Tools discovered: {len(tools_response.tools)}")
            
            if tools_response.tools:
                for tool in tools_response.tools[:5]:  # Show first 5
                    print(f"     - {tool.name}")
                if len(tools_response.tools) > 5:
                    print(f"     ... and {len(tools_response.tools) - 5} more")
            
            print(f"\n✅ {transport_name} WORKS!")
            return True
            
    except Exception as e:
        print(f"   ✗ Failed: {type(e).__name__}")
        print(f"   Error: {str(e)[:200]}")
        
        # If it's an ExceptionGroup, show the underlying exceptions
        if hasattr(e, 'exceptions'):
            print(f"   Underlying errors:")
            for sub_e in e.exceptions:
                print(f"     - {type(sub_e).__name__}: {sub_e}")
        
        return False


async def main():
    """Test all available transports."""
    url = "https://slide.mintlify.app/mcp"
    
    print("="*70)
    print("MCP Transport Discovery Test")
    print("="*70)
    print(f"\nTarget: {url}")
    print("Strategy: Try all MCP transports to find what works\n")
    
    results = {}
    
    # Test 1: SSE (traditional Server-Sent Events)
    results['SSE'] = await test_transport(
        "SSE (Server-Sent Events)",
        sse_client(url),
        url
    )
    
    # Test 2: Streamable HTTP (newer HTTP-based transport)
    results['Streamable HTTP'] = await test_transport(
        "Streamable HTTP",
        streamablehttp_client(url),
        url
    )
    
    # Test 3: WebSocket (if available)
    if WEBSOCKET_AVAILABLE:
        ws_url = url.replace('https://', 'wss://').replace('http://', 'ws://')
        results['WebSocket'] = await test_transport(
            "WebSocket",
            websocket_client(ws_url),
            ws_url
        )
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    for transport, success in results.items():
        status = "✅ WORKS" if success else "❌ FAILED"
        print(f"{transport:20s} {status}")
    
    working = [t for t, s in results.items() if s]
    if working:
        print(f"\n🎉 Working transport(s): {', '.join(working)}")
        print(f"\nAction: Update Tyler to use '{working[0]}' for Mintlify servers")
    else:
        print(f"\n⚠️  None of the transports worked.")
        print("Possible reasons:")
        print("  - Server requires authentication")
        print("  - Server URL is incorrect")
        print("  - Server not publicly accessible")


if __name__ == "__main__":
    asyncio.run(main())
