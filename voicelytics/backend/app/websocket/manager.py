import asyncio


class ConnectionManager:
    def __init__(self):
        self.connections = {}

    async def connect(self, websocket, user_id):
        await websocket.accept()
        self.connections[websocket] = user_id

    def disconnect(self, websocket):
        self.connections.pop(websocket, None)

    async def publish(self):
        # Invalidation contains no private records. Every refetch is authorized by the API.
        for websocket in list(self.connections):
            try:
                await asyncio.wait_for(websocket.send_json({'type': 'records_changed'}), timeout=2)
            except Exception:
                self.disconnect(websocket)


manager = ConnectionManager()
