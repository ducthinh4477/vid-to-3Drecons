from __future__ import annotations

import argparse
import os
import socket
import threading
import time
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the exported visual demo layer.")
    parser.add_argument("--scene", required=True, help="Scene name, for example scene01.")
    parser.add_argument("--policy", required=True, help="Frame filtering policy, for example light_filter.")
    parser.add_argument("--port", default=8088, type=int, help="Preferred local server port.")
    parser.add_argument("--host", default="127.0.0.1", help="Local host.")
    parser.add_argument("--viewer", choices=["local", "supersplat"], default="local", help="Viewer to open.")
    parser.add_argument("--no-open", action="store_true", help="Serve only; do not open a browser.")
    return parser.parse_args()


def demo_dir(scene: str, policy: str) -> Path:
    return ROOT / "outputs" / "demo" / f"{scene}_{policy}"


def find_free_port(host: str, preferred_port: int) -> int:
    for port in range(preferred_port, preferred_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"Could not find a free port near {preferred_port}.")


class DemoHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "cross-origin")
        super().end_headers()

    def log_message(self, format: str, *args: object) -> None:
        print(f"[demo] {self.address_string()} - {format % args}")


def viewer_url(base_url: str, viewer: str) -> str:
    if viewer == "supersplat":
        return f"{base_url}/viewer/index.html?content=/point_cloud.ply&settings=/settings.json"
    return f"{base_url}/?scene=/demo_manifest.json"


def main() -> int:
    args = parse_args()
    output_dir = demo_dir(args.scene, args.policy)
    if not output_dir.exists():
        print(f"Error: demo folder not found: {output_dir}")
        print("Run scripts/12_collect_3dgs_output.py and scripts/13_export_demo_assets.py first.")
        return 1
    if not (output_dir / "point_cloud.ply").exists():
        print("Error: 3DGS output not found; train 3DGS first.")
        print(f"Missing: {output_dir / 'point_cloud.ply'}")
        return 1
    if args.viewer == "local" and not (output_dir / "index.html").exists():
        print(f"Error: local viewer not exported in: {output_dir}")
        print("Run `npm run build` in viewer/, then run scripts/13_export_demo_assets.py again.")
        return 1
    if args.viewer == "supersplat" and not (output_dir / "viewer" / "index.html").exists():
        print(f"Error: SuperSplat viewer not exported in: {output_dir / 'viewer'}")
        print("Run `npm install` in viewer/, then run scripts/13_export_demo_assets.py again.")
        return 1

    port = find_free_port(args.host, args.port)
    handler = partial(DemoHandler, directory=str(output_dir))
    server = ThreadingHTTPServer((args.host, port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://{args.host}:{port}"
    url = viewer_url(base_url, args.viewer)
    print(f"Serving demo folder: {output_dir}")
    print(f"Local viewer URL: {viewer_url(base_url, 'local')}")
    print(f"SuperSplat URL: {viewer_url(base_url, 'supersplat')}")

    if not args.no_open:
        time.sleep(0.8)
        webbrowser.open(url)

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping demo server...")
        return 0
    finally:
        server.shutdown()
        os.chdir(str(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
