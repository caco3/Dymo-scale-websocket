import time
import json
import threading
from dymoscale import DymoScale
from simple_websocket_server import WebSocketServer, WebSocket

READ_TIMEOUT = 2.0  # seconds without a report before we report NO_SCALE


class myWebsocketServer(WebSocket):
    def handle(self):
        for client in clients:
            if client != self:
                client.send_message(self.address[0] + u' - ' + self.data)

    def connected(self):
        print(self.address, 'connected')
        clients.append(self)

    def handle_close(self):
        clients.remove(self)
        print(self.address, 'closed')


def run_server():
    server = WebSocketServer('0.0.0.0', 8085, myWebsocketServer)
    server.serve_forever()


def broadcast(d):
    msg = json.dumps(d)
    for client in clients:
        try:
            client.send_message(msg)
        except Exception as ex:
            print(f"Failed to send to client: {ex}")


if __name__ == "__main__":
    clients = []

    t = threading.Thread(target=run_server)
    t.start()

    while True:
        # (Re)connect loop: keep retrying until the scale enumerates
        # (it must be plugged in AND powered on).
        while True:
            scale = DymoScale()
            if scale.connect():
                break
            broadcast({"status": "error", "code": "NO_SCALE", "description": "Waage nicht verbunden!"})
            time.sleep(1)

        broadcast({"status": "ok", "weight": 0})
        timed_out = False

        # Report read loop
        while True:
            try:
                report = scale.read_report(timeout=READ_TIMEOUT)
            except Exception as ex:
                print(f"Read error: {ex}")
                scale.disconnect()
                broadcast({"status": "error", "code": "NO_SCALE", "description": "Waage nicht verbunden!"})
                break

            if report is None:
                # No report within the timeout: the scale is present but silent
                # (e.g. powered off or weight unchanged). Notify once.
                if not timed_out:
                    timed_out = True
                    broadcast({"status": "error", "code": "NO_SCALE", "description": "Waage nicht verbunden!"})
                continue

            timed_out = False
            d = scale.parse_report(report)

            if d is not None and "weight" in d:
                broadcast({"status": "ok", "weight": d["weight"]})
            elif d is not None and "code" in d:
                broadcast({"status": "error", "code": d["code"], "description": d["description"]})
            else:
                broadcast({"status": "error", "code": "NO_DATA", "description": "Keine Daten verfügbar!"})

        time.sleep(1)
