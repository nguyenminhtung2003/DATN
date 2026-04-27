"""DrowsiGuard WebSocket client with offline-first queue flushing."""
import importlib
import json
import os
import sys
import threading
import time

from utils.logger import get_logger
import config

logger = get_logger("network.ws_client")


def _import_websocket_module(vendor_dir=None):
    try:
        return importlib.import_module("websocket")
    except ImportError:
        vendor_dir = vendor_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "third_party",
        )
        if vendor_dir not in sys.path:
            sys.path.insert(0, vendor_dir)
        try:
            return importlib.import_module("websocket")
        except ImportError:
            return None


websocket = _import_websocket_module()


class WSClient:
    """WebSocket client with auto-reconnect and local queue support."""

    def __init__(self, on_command=None, local_queue=None, on_connect_snapshot=None, on_connect_callback=None):
        self._url = config.WS_SERVER_URL
        self._on_command = on_command
        self._local_queue = local_queue
        self._on_connect_snapshot = on_connect_snapshot
        self._on_connect_callback = on_connect_callback
        self._connected = False
        self._running = False
        self._ws_thread = None
        self._flush_thread = None
        self._reconnect_delay = config.WS_RECONNECT_BASE
        self.ws = None
        logger.info("WSClient initialized target=%s", self._url)

    def start(self):
        if not config.FEATURES.get("websocket"):
            logger.info("WebSocket disabled via feature flag")
            return
        if websocket is None:
            logger.error("websocket-client is not installed; WebSocket integration disabled")
            return

        logger.info("WSClient starting")
        self._running = True
        self._ws_thread = threading.Thread(target=self._ws_loop, daemon=True, name="WSClient")
        self._ws_thread.start()

        if self._local_queue:
            self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True, name="WSFlush")
            self._flush_thread.start()

    def stop(self):
        self._running = False
        if self.ws:
            self.ws.close()
        self._connected = False

    def send(self, msg_type, data):
        """Queue a message for sending. The flush loop handles transmission."""
        if self._local_queue:
            self._local_queue.push(msg_type, data)
        else:
            logger.warning("No local queue configured, dropping message type=%s", msg_type)

    @property
    def is_connected(self):
        return self._connected

    def _ws_loop(self):
        websocket.enableTrace(False)
        while self._running:
            self.ws = websocket.WebSocketApp(
                self._url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )
            self.ws.run_forever(ping_interval=10, ping_timeout=5)

            if self._running:
                logger.warning(
                    "WSClient disconnected. Queue buffering offline events. Reconnecting in %ss",
                    self._reconnect_delay,
                )
                time.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, config.WS_RECONNECT_MAX)

    def _on_open(self, ws):
        logger.info("WSClient connected to backend")
        self._connected = True
        self._reconnect_delay = config.WS_RECONNECT_BASE
        self._send_connect_snapshot(ws)
        if self._on_connect_callback:
            try:
                self._on_connect_callback()
            except Exception as exc:
                logger.warning("WSClient on_connect_callback failed: %s", exc)

    def _send_connect_snapshot(self, ws):
        if not self._on_connect_snapshot:
            return
        try:
            snapshot = self._on_connect_snapshot()
            if snapshot:
                ws.send(json.dumps({"type": "hardware", "data": snapshot}))
        except Exception as exc:
            logger.warning("WSClient failed to send connect snapshot: %s", exc)

    def _on_message(self, ws, message):
        logger.debug("WSClient received command: %s", message)
        if not self._on_command:
            return
        try:
            cmd = json.loads(message)
            self._on_command(cmd)
        except Exception as exc:
            logger.error("WSClient error parsing command: %s", exc)

    def _on_error(self, ws, error):
        logger.warning("WSClient error: %s", error)

    def _on_close(self, ws, close_status_code, close_msg):
        logger.info("WSClient closed code=%s msg=%s", close_status_code, close_msg)
        self._connected = False

    def _flush_loop(self):
        """Continuously check local queue and flush when connected."""
        while self._running:
            if not self._connected or not self.ws:
                time.sleep(1.0)
                continue

            try:
                if self._local_queue.pending_count > 0:
                    batch = self._local_queue.pop_batch(limit=10)
                    sent_ids = []
                    try:
                        for db_id, payload in batch:
                            self.ws.send(json.dumps(payload))
                            sent_ids.append(db_id)
                    finally:
                        if sent_ids:
                            self._local_queue.mark_sent(sent_ids)
                            self._local_queue.cleanup_sent()
                            logger.info("Flushed %s offline events to backend", len(sent_ids))
                    time.sleep(0.5)
                else:
                    time.sleep(1.0)
            except Exception as exc:
                logger.error("WSClient flush error: %s", exc)
                time.sleep(2.0)
