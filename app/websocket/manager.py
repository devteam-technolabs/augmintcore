class ConnectionManager:
    def __init__(self):
        self.active_connections = {}

    async def connect(self, user_id, websocket):
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    def get(self, user_id):
        return self.active_connections.get(user_id)

manager = ConnectionManager()