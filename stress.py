"""stress-app: a CONTROLLED CPU load generator used as the sandbox target for the live demo.

Run in a second terminal:   python stress.py
It burns CPU on all cores and exposes a tiny control API on 127.0.0.1:9100 only:
  GET  /status    -> workers, pids, throttled
  POST /mitigate  -> pauses the CPU-heavy workers (this is what the agent's allowlisted action calls)
  POST /reset     -> resumes the load
Press Ctrl+C to stop everything.
"""
import argparse
import json
import multiprocessing as mp
import os
import signal
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


def worker(flag):
    try:
        while True:
            if flag.is_set():
                time.sleep(0.2)
                continue
            t = time.perf_counter()
            while time.perf_counter() - t < 0.1:
                pass
    except KeyboardInterrupt:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--port", type=int, default=9100)
    a = ap.parse_args()
    flag = mp.Event()
    procs = [mp.Process(target=worker, args=(flag,), daemon=True) for _ in range(a.workers)]
    for p in procs:
        p.start()

    class H(BaseHTTPRequestHandler):
        def _send(self, obj, code=200):
            b = json.dumps(obj).encode()
            self.send_response(code); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

        def do_GET(self):
            if self.path == "/status":
                self._send(dict(workers=a.workers, pids=[p.pid for p in procs], throttled=flag.is_set()))
            else:
                self._send(dict(error="not found"), 404)

        def do_POST(self):
            if self.path == "/mitigate":
                flag.set(); self._send(dict(ok=True, throttled=True))
            elif self.path == "/reset":
                flag.clear(); self._send(dict(ok=True, throttled=False))
            else:
                self._send(dict(error="not found"), 404)

        def log_message(self, *args):
            pass

    signal.signal(signal.SIGTERM, lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()))
    print(f"stress-app running: {a.workers} CPU workers, control API on http://127.0.0.1:{a.port}  (Ctrl+C to stop)")
    try:
        HTTPServer(("127.0.0.1", a.port), H).serve_forever()
    except KeyboardInterrupt:
        print("stopping")
    finally:
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    mp.freeze_support()
    main()