"""3D 火箭点云动画（pygame 地面网格 + 发射版，离屏渲染导出 GIF）

对应你提供的最新 pygame 脚本：地面网格、近大远小点、尾翼双面、点火抖动与发射。
原脚本使用 FULLSCREEN 实时循环；这里改为 SDL dummy 离屏渲染 13.5 秒后合成 GIF。
不覆盖此前任何脚本。
"""

import math
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame
from PIL import Image

pygame.init()

W, H = 900, 900
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("3D Rocket - Point Cloud")

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
FPS = 24
T_END = 13.5
N_FRAMES = int(T_END * FPS)
OUT_SIZE = 480

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

rng = np.random.default_rng(7)


# ============================================================
# 火箭点云：圆柱 + 鼻锥 + 4 尾翼 + 喷口
# cull_mask: True 参与背面剔除，False 双面可见
# ============================================================
def generate_rocket():
    pts, nrm, cull = [], [], []
    R = 12
    BODY_H = 120
    NOSE_H = 40
    n_th = 56
    n_y = 40

    # 圆柱
    for i in range(n_th):
        th = 2 * math.pi * i / n_th
        c, s = math.cos(th), math.sin(th)
        for j in range(n_y + 1):
            y = j * BODY_H / n_y
            pts.append([R * c, y, R * s])
            nrm.append([c, 0.0, s])
            cull.append(True)

    # 鼻锥
    for i in range(n_th):
        th = 2 * math.pi * i / n_th
        c, s = math.cos(th), math.sin(th)
        for j in range(1, 14):
            t = j / 13
            rr = R * (1 - t)
            y = BODY_H + t * NOSE_H
            slope = R / NOSE_H
            nl = math.sqrt(1 + slope * slope)
            pts.append([rr * c, y, rr * s])
            nrm.append([c / nl, slope / nl, s / nl])
            cull.append(True)
    pts.append([0.0, BODY_H + NOSE_H, 0.0])
    nrm.append([0.0, 1.0, 0.0])
    cull.append(True)

    # 4 片尾翼：双面可见，不剔除
    for k in range(4):
        ang = k * math.pi / 2
        c, s = math.cos(ang), math.sin(ang)
        for i in range(9):
            for j in range(11):
                r = R + 20 * i / 8
                y = 40 * j / 10
                pts.append([r * c, y, r * s])
                nrm.append([c, 0.0, s])
                cull.append(False)

    # 喷口
    for i in range(n_th):
        th = 2 * math.pi * i / n_th
        c, s = math.cos(th), math.sin(th)
        for j in range(1, 7):
            t = j / 6
            rr = R * (0.5 + 0.5 * t)
            y = -t * 15
            pts.append([rr * c, y, rr * s])
            nrm.append([c, -0.3, s])
            cull.append(True)

    return (np.array(pts, dtype=np.float64),
            np.array(nrm, dtype=np.float64),
            np.array(cull, dtype=bool))


points, normals, cull_mask = generate_rocket()
print(f"Rocket points: {len(points)}")

# ============================================================
# 地面网格
# ============================================================
grid_pts = np.array([[i * 15.0, -0.2, j * 15.0]
                     for i in range(-8, 9) for j in range(-8, 9)],
                    dtype=np.float64)
grid_norm = np.tile([0.0, 1.0, 0.0], (len(grid_pts), 1))
grid_cull = np.ones(len(grid_pts), dtype=bool)

FOCAL = 740.0


def smoothstep(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


T_ROTATE_END = 8.0
T_LAUNCH_PRE = 10.5
T_LAUNCH_GO = 11.0


def get_camera(t):
    if t < T_ROTATE_END:
        s = smoothstep(t / T_ROTATE_END)
        theta = s * 3 * math.pi
        R = 55 + 205 * s
        cam_y = -35 + 375 * s
    else:
        theta = 3 * math.pi
        R = 260
        cam_y = 340
    cam_pos = np.array([R * math.cos(theta), cam_y, R * math.sin(theta)])
    target = np.array([0.0, 80.0, 0.0])
    return cam_pos, target


def project(pts, nrm, cull, cam_pos, target, focal):
    fwd = target - cam_pos
    fwd = fwd / np.linalg.norm(fwd)
    up_w = np.array([0.0, 1.0, 0.0])
    if abs(np.dot(fwd, up_w)) > 0.999:
        up_w = np.array([0.0, 0.0, 1.0])
    right = np.cross(fwd, up_w)
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)

    d = pts - cam_pos
    x_v = d @ right
    y_v = d @ up
    z_v = d @ fwd

    valid = z_v > 5.0
    z_s = np.where(valid, z_v, 1.0)
    sx = W / 2 + focal * x_v / z_s
    sy = H / 2 - focal * y_v / z_s

    if nrm is not None and cull is not None:
        vv = cam_pos - pts
        dots = np.sum(nrm * vv, axis=1)
        cull_test = np.where(cull, dots > -0.08, True)
        valid = valid & cull_test

    on_screen = (sx >= -5) & (sx < W + 5) & (sy >= -5) & (sy < H + 5)
    valid = valid & on_screen
    return sx, sy, z_v, valid


def generate_flame_points(n, scale):
    t = rng.random(n)
    y = -t * 55 * (0.7 + 0.6 * rng.random(n)) * scale
    r_max = 15 * t * scale
    theta = rng.random(n) * 2 * np.pi
    r = r_max * np.sqrt(rng.random(n))
    return np.column_stack([r * np.cos(theta), y, r * np.sin(theta)])


def draw_cloud(px, py, pz):
    if len(px) == 0:
        return
    radii = np.clip(300.0 / np.maximum(pz, 1.0), 1, 3).astype(int)
    for x, y, r in zip(px, py, radii):
        pygame.draw.circle(screen, BLACK, (int(x), int(y)), int(r))


def render(t):
    cam_pos, target = get_camera(t)

    if t >= T_LAUNCH_GO:
        dtl = t - T_LAUNCH_GO
        launch_y = 0.5 * 300 * dtl * dtl
    else:
        launch_y = 0.0

    shake = 0.0
    if T_LAUNCH_PRE <= t < T_LAUNCH_GO:
        shake = 0.6 * (1 - (t - T_LAUNCH_PRE) / (T_LAUNCH_GO - T_LAUNCH_PRE))

    ox = rng.uniform(-shake, shake) if shake > 0 else 0.0
    oz = rng.uniform(-shake, shake) if shake > 0 else 0.0
    offset = np.array([ox, launch_y, oz])
    rocket_world = points + offset

    screen.fill(WHITE)

    # 网格
    sx, sy, pz, valid = project(grid_pts, grid_norm, grid_cull,
                                cam_pos, target, FOCAL)
    if valid.any():
        px = np.rint(sx[valid]).astype(int)
        py = np.rint(sy[valid]).astype(int)
        for x, y in zip(px, py):
            if 0 <= x < W and 0 <= y < H:
                screen.set_at((int(x), int(y)), BLACK)

    # 火箭
    sx, sy, pz, valid = project(rocket_world, normals, cull_mask,
                                cam_pos, target, FOCAL)
    if valid.any():
        px = np.rint(sx[valid]).astype(int)
        py = np.rint(sy[valid]).astype(int)
        draw_cloud(px, py, pz[valid])

    # 尾焰
    if t >= T_LAUNCH_PRE:
        if t < T_LAUNCH_GO:
            prog = (t - T_LAUNCH_PRE) / (T_LAUNCH_GO - T_LAUNCH_PRE)
            scale = 0.25 + 0.75 * prog
            n_flame = int(60 + 240 * prog)
        else:
            scale = 1.0
            n_flame = 300
        flame_local = generate_flame_points(n_flame, scale)
        base = np.array([ox, launch_y - 15.0, oz])
        flame_world = flame_local + base
        fx, fy, fz, fvalid = project(flame_world, None, None,
                                     cam_pos, target, FOCAL)
        if fvalid.any():
            fpx = np.rint(fx[fvalid]).astype(int)
            fpy = np.rint(fy[fvalid]).astype(int)
            for x, y in zip(fpx, fpy):
                if 0 <= x < W and 0 <= y < H:
                    pygame.draw.circle(screen, BLACK, (int(x), int(y)), 1)

    return pygame.image.tostring(screen, "RGB")


# ============================================================
# 逐帧离屏渲染
# ============================================================
frames = []
for idx in range(N_FRAMES):
    raw = render(idx / FPS)
    img = Image.frombytes("RGB", (W, H), raw)
    img = img.resize((OUT_SIZE, OUT_SIZE), Image.LANCZOS)
    frames.append(img.convert("P", palette=Image.ADAPTIVE, colors=32))

preview_path = os.path.join(OUT_DIR, "rocket_cloud_grid_preview.png")
frames[int(9.0 * FPS)].save(preview_path)

out_path = os.path.join(OUT_DIR, "rocket_cloud_grid.gif")
frames[0].save(out_path, save_all=True, append_images=frames[1:],
               duration=int(1000 / FPS), loop=0, optimize=True)

pygame.quit()

print(f"saved: {out_path}")
print(f"preview: {preview_path}")
print(f"frames: {N_FRAMES}")
