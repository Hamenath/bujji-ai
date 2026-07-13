import logging
from typing import Dict, List, Any
from fastapi import WebSocket

logger = logging.getLogger("app.websocket.connection_manager")

class ConnectionManager:
    """Manages active WebSocket connections to conversations, routing events cleanly."""

    def __init__(self):
        # Maps conversation_id -> list of active WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, conversation_id: str) -> None:
        """Accepts a WebSocket connection and registers it under the conversation ID."""
        await websocket.accept()
        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id] = []
        self.active_connections[conversation_id].append(websocket)
        logger.debug(f"Registered new WS client for conversation: {conversation_id}")

    def disconnect(self, websocket: WebSocket, conversation_id: str) -> None:
        """Unregisters a disconnected WebSocket client."""
        if conversation_id in self.active_connections:
            if websocket in self.active_connections[conversation_id]:
                self.active_connections[conversation_id].remove(websocket)
                logger.debug(f"Unregistered WS client for conversation: {conversation_id}")
            # Clean up empty list keys to prevent memory leaks
            if not self.active_connections[conversation_id]:
                self.active_connections.pop(conversation_id, None)

    async def send_json_event(self, websocket: WebSocket, event_type: str, data: Any) -> None:
        """Sends a single structured JSON event message to a client."""
        try:
            await websocket.send_json({
                "type": event_type,
                "data": data
            })
        except Exception as e:
            logger.error(f"Failed to send WS JSON event '{event_type}': {e}")

    async def broadcast(self, conversation_id: str, event_type: str, data: Any) -> None:
        """Broadcasts a structured JSON event to all clients connected to a specific conversation."""
        if conversation_id in self.active_connections:
            # Create a copy of the list to iterate to avoid issues if connections are modified
            for connection in list(self.active_connections[conversation_id]):
                try:
                    await connection.send_json({
                        "type": event_type,
                        "data": data
                    })
                except Exception as e:
                    logger.error(f"Broadcast failed to WS client in {conversation_id}: {e}")

# Global connection manager instance
connection_manager = ConnectionManager()
