# 3D 火箭发射动画集（Python）

本工程按迭代顺序收录了 6 个版本的火箭发射动画脚本与对应渲染产物，覆盖 2D 动画、
matplotlib 3D 场景、pygame 点云渲染三种实现，全部可在无窗口环境下离线导出 GIF/MP4。

## 环境

- Python 3.11.4
- 虚拟环境：`.venv`
- 依赖：`numpy`、`matplotlib`、`pillow`、`pygame`

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> `requirements.txt` 初始为空，实际安装依赖：
> `pip install numpy matplotlib pillow pygame`

## 版本顺序

| # | 脚本 | 实现方式 | 产物 | 说明 |
|---|------|----------|------|------|
| 1 | `rocket.py` | matplotlib 2D | `rocket_launch.gif` | 2D 星空 + 云层视差、倒计时、点火、烟雾、HUD，16s / 30fps |
| 2 | `rocket3d.py` | matplotlib 3D | `rocket_launch_3d.gif` | 用 mplot3d 复刻 vpython 场景（发射台、塔架、星空、尾焰、烟雾），13s / 20fps |
| 3 | `rocket3d_orbit.py` | matplotlib 3D | `rocket_launch_3d_orbit.gif` | 增加相机环绕、地面网格、加强筋、3D 烟雾；**已知问题：画面主体偏小**，视野受数据范围影响 |
| 4 | `rocket_cloud.py` | pygame 点云 | `rocket_cloud.gif` | 6333 点云 + 透视投影 + 相机推拉（近景仰视 → 拉远俯视），12s / 24fps |
| 5 | `rocket_cloud_launch.py` | pygame 点云 | `rocket_cloud_launch.gif` | 4117 点云 + 相机环绕 0→3π + 背面剔除 + 点火发射，18s / 24fps |
| 6 | `rocket_cloud_grid.py` | pygame 点云 | `rocket_cloud_grid.gif` | 3757 点云 + 地面网格 + 双面尾翼 + 点火抖动 + 发射，13.5s / 24fps |

## 运行

```powershell
# 2D 动画
.\.venv\Scripts\python.exe rocket.py

# matplotlib 3D
.\.venv\Scripts\python.exe rocket3d.py
.\.venv\Scripts\python.exe rocket3d_orbit.py

# pygame 点云（无头渲染，自动导出 GIF）
.\.venv\Scripts\python.exe rocket_cloud.py
.\.venv\Scripts\python.exe rocket_cloud_launch.py
.\.venv\Scripts\python.exe rocket_cloud_grid.py
```

所有脚本自动将产物写入脚本所在目录：

- matplotlib 版本优先生成 MP4（需要 ffmpeg），缺少 ffmpeg 时回退 GIF
- pygame 版本通过 `SDL_VIDEODRIVER=dummy` 离屏渲染，逐帧截图后用 Pillow 合成 GIF
- `rocket3d_orbit.py`、`rocket_cloud.py`、`rocket_cloud_launch.py`、`rocket_cloud_grid.py`
  会额外输出同名 `*_preview.png` 中间帧，便于快速检查构图

## 产物文件

| 文件 | 说明 |
|------|------|
| `rocket_launch.gif` | 版本 1 产物（2D） |
| `rocket_launch_3d.gif` | 版本 2 产物（3D） |
| `rocket_launch_3d_orbit.gif` | 版本 3 产物（3D 环绕） |
| `rocket3d_orbit_preview.png` | 版本 3 中间帧 |
| `rocket_cloud.gif` | 版本 4 产物（点云） |
| `rocket_cloud_preview.png` | 版本 4 中间帧 |
| `rocket_cloud_launch.gif` | 版本 5 产物（点云环绕发射） |
| `rocket_cloud_launch_preview.png` | 版本 5 中间帧 |
| `rocket_cloud_grid.gif` | 版本 6 产物（点云网格发射） |
| `rocket_cloud_grid_preview.png` | 版本 6 中间帧 |

## 技术要点

- **2D 版**：`FuncAnimation` + `PillowWriter`/`FFMpegWriter`，世界坐标平移实现摄像机跟随
- **matplotlib 3D 版**：手工构造圆柱/圆锥/长方体网格顶点，用 `Poly3DCollection` 绘制；
  每帧重建场景，`cam` 高度通过坐标平移实现跟随
- **pygame 点云版**：
  - 参数化生成火箭点云（圆柱、鼻锥、尾翼、喷口）及法向
  - 自写透视投影：视图矩阵（forward/right/up）+ 焦距缩放
  - 背面剔除：`dot(normal, cam_pos - point) > threshold`
  - 近大远小：点半径 `clip(300 / depth, 1, 3)`
  - 相机动画：`smoothstep` 插值位置、环绕角度、推拉距离

## 已知问题

- `rocket3d_orbit.py` 的构图受 mplot3d 数据范围影响，主体偏小，未完全修复
- 所有动画在火箭升空后使用固定或跟随不足的镜头，末段本体可能飞出画面

## 许可

仅用于演示与学习。
