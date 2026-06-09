from __future__ import annotations

import argparse
import json
import mimetypes
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlparse


ROOT = Path(__file__).resolve().parents[1]
VIEWER_DIR = ROOT / "viewer"
COMMON_NPM_PATHS = [
    Path("C:/Program Files/nodejs/npm.cmd"),
    Path("C:/Program Files (x86)/nodejs/npm.cmd"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the local FPS 3DGS viewer.")
    parser.add_argument("--scene-json", required=True, type=Path, help="viewer_scene.json produced by script 13.")
    parser.add_argument("--host", default="127.0.0.1", help="Local host.")
    parser.add_argument("--viewer-port", default=5173, type=int, help="Preferred Vite viewer port.")
    parser.add_argument("--asset-port", default=8765, type=int, help="Preferred asset server port.")
    parser.add_argument("--no-open", action="store_true", help="Do not open the browser automatically.")
    parser.add_argument("--install-viewer-deps", action="store_true", help="Run npm install if node_modules is missing.")
    return parser.parse_args()


def find_free_port(host: str, preferred_port: int) -> int:
    for port in range(preferred_port, preferred_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"Could not find a free port near {preferred_port}.")


def load_scene(scene_json_path: Path) -> dict:
    with scene_json_path.open("r", encoding="utf-8") as f:
        scene = json.load(f)
    splat_path = scene.get("splat")
    if not splat_path:
        raise ValueError("viewer_scene.json is missing the `splat` path.")
    resolved_splat = Path(splat_path)
    if not resolved_splat.exists():
        raise FileNotFoundError(f"Splat PLY not found: {resolved_splat}")
    return scene


def make_preview_points(path: Path, max_points: int = 60000) -> bytes | None:
    try:
        import numpy as np
        from plyfile import PlyData
    except Exception:
        return None

    try:
        vertex = PlyData.read(str(path))["vertex"].data
    except Exception:
        return None

    names = set(vertex.dtype.names or [])
    if not {"x", "y", "z"}.issubset(names) or len(vertex) == 0:
        return None

    count = len(vertex)
    step = max(count // max_points, 1)
    sampled = vertex[::step][:max_points]
    positions = np.column_stack(
        [
            np.asarray(sampled["x"], dtype=np.float32),
            np.asarray(sampled["y"], dtype=np.float32),
            np.asarray(sampled["z"], dtype=np.float32),
        ]
    )

    if {"f_dc_0", "f_dc_1", "f_dc_2"}.issubset(names):
        colors = np.column_stack(
            [
                np.asarray(sampled["f_dc_0"], dtype=np.float32),
                np.asarray(sampled["f_dc_1"], dtype=np.float32),
                np.asarray(sampled["f_dc_2"], dtype=np.float32),
            ]
        )
        colors = np.clip(colors * 0.28209479177387814 + 0.5, 0.0, 1.0)
    elif {"red", "green", "blue"}.issubset(names):
        colors = np.column_stack(
            [
                np.asarray(sampled["red"], dtype=np.float32),
                np.asarray(sampled["green"], dtype=np.float32),
                np.asarray(sampled["blue"], dtype=np.float32),
            ]
        )
        if np.nanmax(colors) > 1.0:
            colors = colors / 255.0
        colors = np.clip(colors, 0.0, 1.0)
    else:
        colors = np.ones_like(positions, dtype=np.float32)

    preview = {
        "count": int(len(sampled)),
        "positions": positions.reshape(-1).round(5).astype(float).tolist(),
        "colors": colors.reshape(-1).round(4).astype(float).tolist(),
    }
    return json.dumps(preview, separators=(",", ":")).encode("utf-8")


def make_asset_handler(scene: dict, scene_json_path: Path, asset_base_url: str) -> type[BaseHTTPRequestHandler]:
    splat_path = Path(scene["splat"]).resolve()
    preview_points = make_preview_points(splat_path)
    runtime_scene = dict(scene)
    runtime_scene["splat_url"] = f"{asset_base_url}/splat.ply"
    if preview_points is not None:
        runtime_scene["preview_points_url"] = f"{asset_base_url}/preview_points.json"
    runtime_scene["source_scene_json"] = str(scene_json_path.resolve()).replace("\\", "/")
    scene_bytes = json.dumps(runtime_scene, indent=2).encode("utf-8")

    class AssetHandler(BaseHTTPRequestHandler):
        def end_headers(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cross-Origin-Opener-Policy", "same-origin")
            self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
            self.send_header("Cross-Origin-Resource-Policy", "cross-origin")
            super().end_headers()

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.end_headers()

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/scene.json":
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(scene_bytes)))
                self.end_headers()
                self.wfile.write(scene_bytes)
                return
            if path == "/splat.ply":
                self.serve_file(splat_path)
                return
            if path == "/preview_points.json" and preview_points is not None:
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(preview_points)))
                self.end_headers()
                self.wfile.write(preview_points)
                return
            self.send_error(404, "Not found")

        def serve_file(self, path: Path) -> None:
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(path.stat().st_size))
            self.end_headers()
            with path.open("rb") as f:
                shutil.copyfileobj(f, self.wfile)

        def log_message(self, format: str, *args: object) -> None:
            return

    return AssetHandler


def ensure_viewer_ready(install_deps: bool) -> bool:
    if not (VIEWER_DIR / "package.json").exists():
        print(f"Error: viewer package not found: {VIEWER_DIR / 'package.json'}")
        return False
    npm = find_npm()
    if npm is None:
        print("Error: npm not found on PATH.")
        return False
    if install_deps and not (VIEWER_DIR / "node_modules").exists():
        result = subprocess.run([npm, "install"], cwd=str(VIEWER_DIR), env=npm_environment(npm))
        return result.returncode == 0
    if not (VIEWER_DIR / "node_modules").exists():
        print("Error: viewer/node_modules not found. Run `npm install` in viewer/ or pass --install-viewer-deps.")
        return False
    return True


def find_npm() -> str | None:
    npm = shutil.which("npm")
    if npm:
        return npm
    for npm_path in COMMON_NPM_PATHS:
        if npm_path.exists():
            return str(npm_path)
    return None


def npm_environment(npm_path: str) -> dict[str, str]:
    env = os.environ.copy()
    npm_parent = str(Path(npm_path).parent)
    existing_path = env.get("PATH", "")
    env["PATH"] = npm_parent if not existing_path else os.pathsep.join([npm_parent, existing_path])
    return env


def main() -> int:
    args = parse_args()
    if not args.scene_json.exists():
        print(f"Error: scene JSON not found: {args.scene_json}")
        return 1
    if not ensure_viewer_ready(args.install_viewer_deps):
        return 1

    try:
        scene = load_scene(args.scene_json)
        viewer_port = find_free_port(args.host, args.viewer_port)
        asset_port = find_free_port(args.host, args.asset_port)
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    asset_base_url = f"http://{args.host}:{asset_port}"
    handler = make_asset_handler(scene, args.scene_json, asset_base_url)
    asset_server = ThreadingHTTPServer((args.host, asset_port), handler)
    thread = threading.Thread(target=asset_server.serve_forever, daemon=True)
    thread.start()

    npm = find_npm()
    if npm is None:
        print("Error: npm not found on PATH or common Windows install locations.")
        return 1

    vite_command = [
        npm,
        "run",
        "dev",
        "--",
        "--host",
        args.host,
        "--port",
        str(viewer_port),
    ]
    vite = subprocess.Popen(vite_command, cwd=str(VIEWER_DIR), env=npm_environment(npm))
    scene_url = quote(f"{asset_base_url}/scene.json", safe="")
    viewer_url = f"http://{args.host}:{viewer_port}/?scene={scene_url}"

    print(f"Asset server: {asset_base_url}")
    print(f"Viewer URL: {viewer_url}")
    if not args.no_open:
        time.sleep(1.5)
        webbrowser.open(viewer_url)

    try:
        return vite.wait()
    except KeyboardInterrupt:
        print("\nStopping viewer...")
        return 0
    finally:
        asset_server.shutdown()
        if vite.poll() is None:
            vite.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
