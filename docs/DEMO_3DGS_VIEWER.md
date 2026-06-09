# 3DGS Visual Demo Layer

This demo layer packages trained 3D Gaussian Splatting output for browser viewing after a valid COLMAP reconstruction already exists.

It does not replace the project evaluation pipeline. The main report pipeline remains:

```text
video -> frame extraction -> frame quality -> frame selection
-> COLMAP automatic_reconstructor -> COLMAP evaluation
```

3DGS is only a visualization/demo stage after COLMAP camera poses are available.

## Requirements

- A good COLMAP sparse/dense reconstruction must exist first.
- `outputs/reconstructions/<scene>/<policy>/colmap` should contain usable COLMAP output.
- The project currently reports COLMAP automatic_reconstructor results, not hloc/SuperPoint/LightGlue results.
- A trained 3DGS `point_cloud.ply` must exist before collecting demo output.
- Run `npm install` in `viewer/` so `@playcanvas/supersplat-viewer` is available.
- Run `npm run build` in `viewer/` before exporting if you want the local viewer copied into the demo folder.

## Prepare a 3DGS Dataset

From the repository root:

```powershell
python scripts/11_prepare_3dgs_dataset.py --scene scene01 --policy light_filter --overwrite
```

Default output:

```text
data/3dgs/scene01_light/
```

## Train 3DGS

Train with your 3DGS implementation. Example command from a Gaussian Splatting checkout:

```powershell
python train.py -s C:\GitHub\vid-to-3Drecons\data\3dgs\scene01_light -m output\scene01_light_3dgs_7k --iterations 7000 --resolution 2
```

The trained model should contain a file like:

```text
<model-dir>/point_cloud/iteration_7000/point_cloud.ply
```

## Collect Trained Output

```powershell
python scripts/12_collect_3dgs_output.py --scene scene01 --policy light_filter --model-dir <path-to-gaussian-splatting>\output\scene01_light_3dgs_7k --iteration 7000
```

This creates:

```text
outputs/demo/scene01_light_filter/
  point_cloud.ply
  metrics.json                # copied if available
  demo_manifest.json
```

If the PLY is missing, the script reports:

```text
3DGS output not found; train 3DGS first.
```

## Export Browser Demo Assets

Build and install viewer dependencies first:

```powershell
cd viewer
npm install
npm run build
cd ..
```

Then export:

```powershell
python scripts/13_export_demo_assets.py --scene scene01 --policy light_filter
```

This adds:

```text
outputs/demo/scene01_light_filter/
  settings.json               # SuperSplat Viewer settings
  scene.json                  # local Gaussian viewer scene
  thumbnails/
  viewer/                     # SuperSplat static viewer
  index.html, assets/          # local viewer build, if viewer/dist exists
```

Only representative thumbnails are copied, not the full selected frame set.

## Launch Demo

Local viewer:

```powershell
python scripts/14_launch_demo.py --scene scene01 --policy light_filter
```

SuperSplat Viewer:

```powershell
python scripts/14_launch_demo.py --scene scene01 --policy light_filter --viewer supersplat
```

The launcher serves:

```text
http://127.0.0.1:8088/?scene=/demo_manifest.json
http://127.0.0.1:8088/viewer/index.html?content=/point_cloud.ply&settings=/settings.json
```

## Viewer Notes

- The local viewer uses `@mkkellogg/gaussian-splats-3d`.
- SuperSplat Viewer is provided by the npm package `@playcanvas/supersplat-viewer`.
- ViS-3DGS can still be used separately in VSCode to inspect a PLY.
- SuperSplat, ViS-3DGS, and Gaussian viewers are visualization tools only; they are not the current quantitative evaluation method.

## Optional ViS-3DGS Build

If you maintain a local VSCode extension checkout:

```powershell
cd third_party/vis-3dgs
npm install
npm run build
npm run package
code --install-extension builds/vis-3dgs-viewer.vsix --force
```
