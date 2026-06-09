from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from web.backend.artifact_service import ROOT, VIDEO_EXTENSIONS, list_media_files, read_json, serve_artifact
from web.backend.pipeline_runner import DemoRequest, runner

FRONTEND_DIST = ROOT / "viewer" / "dist"


class DemoStartBody(BaseModel):
    video_path: str = Field(..., min_length=1)
    scene: str = Field(default="scene01")
    policy: str = Field(default="light_filter")
    mode: str = Field(default="instant")
    fps: float = Field(default=5.0, gt=0)
    quality: str = Field(default="medium")
    iterations: int = Field(default=1500, ge=1)
    resolution: int = Field(default=4, ge=1)


app = FastAPI(title="Vid-to-3D Reconstruction Demo")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/", response_model=None)
def index():
    index_path = FRONTEND_DIST / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return RedirectResponse("/api/health")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "frontend_dist": FRONTEND_DIST.exists()}


@app.get("/api/scenes")
def scenes() -> dict:
    videos = []
    for path in list_media_files(ROOT / "data" / "raw_videos", VIDEO_EXTENSIONS):
        videos.append({"scene": path.stem, "video_path": path.relative_to(ROOT).as_posix(), "label": path.name})

    demo_manifests = []
    demo_root = ROOT / "outputs" / "demo"
    if demo_root.exists():
        for manifest in sorted(demo_root.glob("*/demo_manifest.json")):
            try:
                data = read_json(manifest)
            except Exception:
                continue
            demo_manifests.append(
                {
                    "scene": data.get("scene"),
                    "policy": data.get("policy"),
                    "manifest": f"/api/artifacts/{data.get('scene')}/{data.get('policy')}/manifest",
                }
            )
    return {"videos": videos, "demos": demo_manifests}


@app.post("/api/demo/start")
def start_demo(body: DemoStartBody) -> dict:
    if body.mode not in {"instant", "cached", "preview"}:
        raise HTTPException(status_code=400, detail="mode must be instant, cached, or preview")
    request = DemoRequest(
        video_path=body.video_path,
        scene=body.scene,
        policy=body.policy,
        mode=body.mode,  # type: ignore[arg-type]
        fps=body.fps,
        quality=body.quality,
        iterations=body.iterations,
        resolution=body.resolution,
    )
    job = runner.start(request)
    return {"job_id": job.id, "status": "started"}


@app.get("/api/demo/status/{job_id}")
def status(job_id: str) -> dict:
    job = runner.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job.snapshot()


@app.get("/api/demo/events/{job_id}")
async def events(job_id: str) -> StreamingResponse:
    job = runner.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    async def stream():
        yield f"data: {json.dumps(job.snapshot())}\n\n"
        while True:
            try:
                payload = await asyncio.to_thread(job.events.get, True, 15)
                yield f"data: {json.dumps(payload)}\n\n"
                if payload.get("status") in {"done", "error"}:
                    break
            except Exception:
                yield ": keep-alive\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/artifacts/{scene}/{policy}/manifest")
def manifest(scene: str, policy: str) -> dict:
    path = ROOT / "outputs" / "demo" / f"{scene}_{policy}" / "demo_manifest.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="manifest not found")
    return read_json(path)


@app.get("/api/artifacts/file", response_model=None)
def file(path: str):
    return serve_artifact(path)


@app.get("/{path:path}", response_model=None)
def spa_fallback(path: str):
    index_path = FRONTEND_DIST / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="frontend build not found")
