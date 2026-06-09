from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the one-page Vid-to-3D web demo.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8088, type=int)
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser automatically.")
    parser.add_argument("--no-build", action="store_true", help="Serve the existing frontend build.")
    return parser.parse_args()


def find_free_port(host: str, preferred: int) -> int:
    for port in range(preferred, preferred + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"Could not find a free port near {preferred}.")


def ensure_frontend_build(no_build: bool) -> None:
    dist = ROOT / "viewer" / "dist" / "index.html"
    if no_build and not dist.exists():
        raise RuntimeError("viewer/dist/index.html does not exist. Run npm install && npm run build in viewer/.")
    if no_build:
        return
    npm = shutil.which("npm")
    if npm is None:
        npm_cmd = Path("C:/Program Files/nodejs/npm.cmd")
        if npm_cmd.exists():
            npm = str(npm_cmd)
    if npm is None:
        if dist.exists():
            print("npm was not found; serving existing viewer/dist build.")
            return
        raise RuntimeError("npm was not found and viewer/dist is missing.")
    print("Building frontend...")
    env = None
    node_dir = Path(npm).parent
    if (node_dir / "node.exe").exists():
        import os

        env = os.environ.copy()
        env["PATH"] = f"{node_dir};{env.get('PATH', '')}"
    result = subprocess.run([npm, "run", "build"], cwd=ROOT / "viewer", env=env)
    if result.returncode != 0:
        raise RuntimeError(f"Frontend build failed with exit code {result.returncode}.")


def main() -> int:
    args = parse_args()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        ensure_frontend_build(args.no_build)
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is not installed. Run `pip install -r requirements.txt`.")
        return 1

    port = find_free_port(args.host, args.port)
    url = f"http://{args.host}:{port}"
    print(f"One-page web demo: {url}")
    print("This app renders COLMAP preview and cached 3DGS in the same page.")
    if not args.no_open:
        webbrowser.open(url)
    uvicorn.run("web.backend.app:app", host=args.host, port=port, reload=False, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
