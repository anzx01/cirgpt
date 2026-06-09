"""
Socket.io manager for real-time progress updates
"""
import logging
from typing import Dict, List
import asyncio
try:
    from socketio import AsyncServer
except ImportError:
    AsyncServer = None
from models import SessionLocal, CircuitDesign

logger = logging.getLogger(__name__)


class SocketManager:
    """Manage Socket.io connections and events"""

    def __init__(self):
        """Initialize socket manager"""
        if AsyncServer is None:
            self.socket_server = None
            self.active_connections: Dict[str, str] = {}
            logger.warning("python-socketio is not installed; realtime updates are disabled")
            return

        self.socket_server = AsyncServer(async_mode="asgi", cors_allowed_origins="*")
        self.active_connections: Dict[str, str] = {}  # {sid: design_id}

        # Register event handlers
        self._register_handlers()

    def _register_handlers(self):
        """Register Socket.io event handlers"""

        @self.socket_server.event
        async def connect(sid, environ):
            """Handle client connection"""
            logger.info(f"Client connected: {sid}")
            await self.socket_server.emit("connected", {"message": "Connected to circuit design server"}, to=sid)

        @self.socket_server.event
        async def disconnect(sid):
            """Handle client disconnection"""
            logger.info(f"Client disconnected: {sid}")
            if sid in self.active_connections:
                del self.active_connections[sid]

        @self.socket_server.event
        async def subscribe(sid, data):
            """
            Subscribe to design updates

            Args:
                data: {"design_id": int}
            """
            design_id = data.get("design_id")
            if design_id:
                self.active_connections[sid] = design_id
                logger.info(f"Client {sid} subscribed to design {design_id}")

                # Send current status
                await self._send_current_status(sid, design_id)

        @self.socket_server.event
        async def unsubscribe(sid, data):
            """
            Unsubscribe from design updates

            Args:
                data: {"design_id": int}
            """
            design_id = data.get("design_id")
            if sid in self.active_connections and self.active_connections[sid] == design_id:
                del self.active_connections[sid]
                logger.info(f"Client {sid} unsubscribed from design {design_id}")

    async def _send_current_status(self, sid: str, design_id: int):
        """Send current design status to client"""
        db = SessionLocal()
        try:
            design = db.query(CircuitDesign).filter(CircuitDesign.id == design_id).first()
            if design:
                payload = {
                    "design_id": design_id,
                    "status": design.status,
                    "progress": design.progress if design.progress is not None else self._calculate_progress(design.status),
                    "message": design.current_step or self._get_status_message(design.status)
                }
                await self.socket_server.emit(
                    "design.status",
                    payload,
                    to=sid
                )
                await self.socket_server.emit("design_status", payload, to=sid)
        finally:
            db.close()

    def _calculate_progress(self, status: str) -> int:
        """Calculate progress percentage from status"""
        progress_map = {
            "pending": 0,
            "processing": 50,
            "completed": 100,
            "failed": 0
        }
        return progress_map.get(status, 0)

    def _get_status_message(self, status: str) -> str:
        """Get user-friendly status message"""
        message_map = {
            "pending": "Design is pending generation",
            "processing": "Design is being generated...",
            "completed": "Design generation complete!",
            "failed": "Design generation failed"
        }
        return message_map.get(status, "Unknown status")

    async def broadcast_progress(self, design_id: int, message: str, progress: int, error: bool = False):
        """
        Broadcast progress update to all subscribed clients

        Args:
            design_id: Circuit design ID
            message: Progress message
            progress: Progress percentage (0-100)
            error: Whether this is an error message
        """
        # Find all clients subscribed to this design
        if self.socket_server is None:
            return

        target_sids = [sid for sid, did in self.active_connections.items() if did == design_id]

        if target_sids:
            event_type = "design.failed" if error else "design.progress"
            legacy_event_type = "design_error" if error else "design_progress"
            payload = {
                "design_id": design_id,
                "message": message,
                "progress": progress,
                "timestamp": asyncio.get_event_loop().time()
            }

            await self.socket_server.emit(
                event_type,
                payload,
                to=target_sids
            )
            await self.socket_server.emit(legacy_event_type, payload, to=target_sids)

            logger.info(f"Broadcasted progress to {len(target_sids)} clients for design {design_id}")

    async def broadcast_complete(self, design_id: int):
        """
        Broadcast design completion

        Args:
            design_id: Circuit design ID
        """
        if self.socket_server is None:
            return

        target_sids = [sid for sid, did in self.active_connections.items() if did == design_id]
        payload = {"design_id": design_id, "message": "Design generation complete!", "progress": 100}
        if target_sids:
            await self.socket_server.emit("design.completed", payload, to=target_sids)
        await self.broadcast_progress(design_id, "Design generation complete!", 100)

    async def broadcast_error(self, design_id: int, error_message: str):
        """
        Broadcast design error

        Args:
            design_id: Circuit design ID
            error_message: Error message
        """
        await self.broadcast_progress(design_id, error_message, 0, error=True)

    def get_app(self):
        """Get ASGI app for mounting"""
        return self.socket_server


# Global socket manager instance
socket_manager = SocketManager()


async def notify_progress(design_id: int, message: str, progress: int, error: bool = False):
    """
    Helper function to notify progress from anywhere in the app

    Args:
        design_id: Circuit design ID
        message: Progress message
        progress: Progress percentage (0-100)
        error: Whether this is an error message
    """
    await socket_manager.broadcast_progress(design_id, message, progress, error)


async def notify_complete(design_id: int):
    """Helper function to notify completion"""
    await socket_manager.broadcast_complete(design_id)


async def notify_error(design_id: int, error_message: str):
    """Helper function to notify error"""
    await socket_manager.broadcast_error(design_id, error_message)
