import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8001/api/voice/ws/test-conversation-123"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Successfully connected!")
            
            # Since the backend expects some interaction or just proxies,
            # we can send a simple text payload to see if it handles it or crashes
            test_payload = {"test": "hello"}
            await websocket.send(json.dumps(test_payload))
            print("Sent test payload")
            
            # Wait a tiny bit to see if server closes or sends something back
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                print(f"Received response: {response}")
            except asyncio.TimeoutError:
                print("No immediate response (timeout), which is normal for this proxy if no audio was sent.")
            
            print("Websocket test completed successfully.")
            
    except Exception as e:
        print(f"Websocket connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
