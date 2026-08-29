from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from app.core.security import decode_access_token, TokenError
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orbit", tags=["orbit-ws"])


class OrbitConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(
                f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast_orbit_updates(self, updates: List[Dict]):
        if not self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json({"type": "ORBIT_UPDATE", "data": updates})
            except Exception as e:
                logger.error(f"Error broadcasting to websocket: {e}")
                disconnected.append(connection)

        for d in disconnected:
            self.disconnect(d)


orbit_manager = OrbitConnectionManager()


@router.websocket("/ws")
async def orbit_websocket_endpoint(websocket: WebSocket, token: str = Query(None)):
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    try:
        decode_access_token(token)
    except TokenError as e:
        logger.error(f"WebSocket auth failed: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await orbit_manager.connect(websocket)
    try:
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        orbit_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        orbit_manager.disconnect(websocket)
