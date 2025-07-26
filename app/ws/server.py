import asyncio
import websockets
import json

class WebSocketServer:
    """
    Manages WebSocket connections from frontend clients and broadcasts data.
    """
    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.clients = set()  # A set to store all connected clients
        self.server = None
        print("WebSocket Server initialized.")

    async def start(self):
        """Starts the WebSocket server."""
        self.server = await websockets.serve(self._handler, self.host, self.port)
        print(f"WebSocket Server listening on ws://{self.host}:{self.port}")
        await self.server.wait_closed()

    async def _handler(self, websocket):
        """
        Handles a new client connection.
        """
        # Register the new client
        self.clients.add(websocket)
        print(f"New client connected. Total clients: {len(self.clients)}")
        try:
            # Keep the connection open and listen for messages (if any)
            async for message in websocket:
                # We can add logic here if the frontend needs to send data
                # For now, we just print it
                print(f"Received message from client: {message}")
        except websockets.exceptions.ConnectionClosed:
            print("Client connection closed.")
        finally:
            # Unregister the client when they disconnect
            self.clients.remove(websocket)
            print(f"Client disconnected. Total clients: {len(self.clients)}")

    async def broadcast(self, message):
        """
        Sends a message to all connected clients.
        """
        if not self.clients:
            return  # No clients to send to

        # We convert the Python dictionary to a JSON string before sending
        json_message = json.dumps(message)
        
        # We use asyncio.gather to send messages to all clients concurrently
        # This is much more efficient than looping and sending one by one
        await asyncio.gather(
            *[client.send(json_message) for client in self.clients]
        )

    async def stop(self):
        """Stops the WebSocket server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            print("WebSocket Server stopped.")