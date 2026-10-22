"""3D 火箭点云动画（pygame 环绕 + 发射版，离屏渲染导出 GIF）

对应你提供的 pygame 脚本：点云火箭、相机环绕、背面剔除、点火与尾焰、发射升空。
原脚本使用 FULLSCREEN + 实时循环；这里改为 SDL dummy 离屏渲染，按 24fps 逐帧渲染
18 秒后合成 GIF，无需交互窗口。不覆盖此前任何脚本。
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
DURATION = 18.0
N_FRAMES = int(DURATION * FPS)
OUT_SIZE = 480


def generate_rocket():
    pts, nrm = [], []
    R = 12
    BODY_H = 120
    NOSE_H = 40
    n_th = 60
    n_y = 40

    for i in range(n_th):
        th = 2 * math.pi * i / n_th
        c, s = math.cos(th), math.sin(th)
        for j in range(n_y + 1):
            y = j * BODY_H / n_y
            pts.append([R * c, y, R * s])
            nrm.append([c, 0.0, s])

    for i in range(n_th):
        th = 2 * math.pi * i / n_th
        c, s = math.cos(th), math.sin(th)
        for j in range(1, 16):
            t = j / 15
            rr = R * (1 - t)
            y = BODY_H + t * NOSE_H
            pts.append([rr * c, y, rr * s])
            slope = R / NOSE_H
            nl = math.sqrt(1 + slope * slope)
            nrm.append([c / nl, slope / nl, s / nl])
    pts.append([0.0, BODY_H + NOSE_H, 0.0])
    nrm.append([0.0, 1.0, 0.0])

    for k in range(4):
        ang = k * math.pi / 2
        c, s = math.cos(ang), math.sin(ang)
        for i in range(9):
            for j in range(11):
                r = R + 20 * i / 8
                y = 40 * j / 10
                pts.append([r * c, y, r * s])
                nrm.append([c, 0.0, s])

    for i in range(n_th):
        th = 2 * math.pi * i / n_th
        c, s = math.cos(th), math.sin(th)
        for j in range(1, 7):
            t = j / 6
            rr = R * (0.5 + 0.5 * t)
            y = -t * 15
            pts.append([rr * c, y, rr * s])
            nrm.append([c, -0.3, s])

    return np.array(pts, dtype=np.float64), np.array(nrm, dtype=np.float64)


points, normals = generate_rocket()
print(f"Points: {len(points)}")

FOCAL = 1200.0


def smoothstep(x):
    return x * x * (3 - 2 * x)


T_ROTATE_END = 8.0
T_LAUNCH_START = 11.0
T_LAUNCH_GO = 11.5


def get_camera(t):
    if t < T_ROTATE_END:
        s = smoothstep(t / T_ROTATE_END)
        theta = s * 3 * math.pi
        R = 100 + 80 * s
        cam_y = -30 + 300 * s
    else:
        theta = 3 * math.pi
        R = 180
        cam_y = 270
    cam_pos = np.array([R * math.cos(theta), cam_y, R * math.sin(theta)])
    target = np.array([0, 80, 0])
    return cam_pos, target


def project(pts, nrm, cam_pos, target, focal):
    fwd = target - cam_pos
    fwd = fwd / np.linalg.norm(fwd)
    up_w = np.array([0.0, 1.0, 0.0])
    if abs(np.dot(fwd, up_w)) > 0.999:
        up_w = np.array([0.0, 0.0, 1.0])
    right = np.cross(fwd, up_w)
    right = right / np.linalg.norm(right)
    up = np.cross(right, fwd)

    d = pts - cam_pos
    x_v = d @ right
    y_v = d @ up
    z_v = d @ fwd

    valid = z_v > 1.0
    z_s = np.where(valid, z_v, 1.0)

    sx = W / 2 + focal * x_v / z_s
    sy = H / 2 - focal * y_v / z_s

    vv = cam_pos - pts
    dots = np.sum(nrm * vv, axis=1)
    valid = valid & (dots > 0)
    valid = valid & (sx >= 0) & (sx < W - 1) & (sy >= 0) & (sy < H - 1)

    return sx, sy, valid


rng = np.random.default_rng(7)


def generate_flame_points(n=250):
    t = rng.random(n)
    y = -t * 55 * (0.7 + 0.6 * rng.random(n))
    r_max = 15 * t
    theta = rng.random(n) * 2 * np.pi
    r = r_max * np.sqrt(rng.random(n))
    return np.column_stack([r * np.cos(theta), y, r * np.sin(theta)])


def render(t):
    if t < T_LAUNCH_GO:
        launch_y = 0.0
        flame_on = False
    else:
        dtl = t - T_LAUNCH_GO
        launch_y = 0.5 * 250 * dtl * dtl
        flame_on = True

    if T_LAUNCH_START <= t < T_LAUNCH_GO:
        flame_on = True
        launch_y = 0.0

    cam_pos, target = get_camera(t)

    rocket_world = points + np.array([0, launch_y, 0])
    sx, sy, valid = project(rocket_world, normals, cam_pos, target, FOCAL)

    pixels = pygame.surfarray.pixels3d(screen)
    pixels[:, :] = 255

    if valid.sum() > 0:
        px = sx[valid].astype(int)
        py = sy[valid].astype(int)
        for dx in (0, 1):
            for dy in (0, 1):
                x = np.clip(px + dx, 0, W - 1)
                y = np.clip(py + dy, 0, H - 1)
                pixels[x, y] = 0

    if flame_on:
        if t < T_LAUNCH_GO:
            base = np.array([0, launch_y - 15, 0])
            intensity = 0.3 + 0.7 * ((t - T_LAUNCH_START) /
                                     (T_LAUNCH_GO - T_LAUNCH_START))
            n_flame = int(80 * intensity)
            flame_local = generate_flame_points(n_flame) * 0.3
        else:
            base = np.array([0, launch_y - 15, 0])
            flame_local = generate_flame_points(250)

        flame_world = flame_local + base
        flame_norm = np.tile([0, 0, 1], (len(flame_world), 1))
        fx, fy, fvalid = project(flame_world, flame_norm,
                                 cam_pos, target, FOCAL)
        if fvalid.sum() > 0:
            fpx = fx[fvalid].astype(int)
            fpy = fy[fvalid].astype(int)
            x = np.clip(fpx, 0, W - 1)
            y = np.clip(fpy, 0, H - 1)
            pixels[x, y] = 0

    del pixels
    return pygame.image.tostring(screen, "RGB")


# ============ 逐帧离屏渲染 ============
frames = []
for idx in range(N_FRAMES):
    raw = render(idx / FPS)
    img = Image.frombytes("RGB", (W, H), raw)
    img = img.resize((OUT_SIZE, OUT_SIZE), Image.LANCZOS)
    frames.append(img.convert("P", palette=Image.ADAPTIVE, colors=32))

preview_path = os.path.join(OUT_DIR, "rocket_cloud_launch_preview.png")
frames[int(10.0 * FPS)].save(preview_path)

out_path = os.path.join(OUT_DIR, "rocket_cloud_launch.gif")
frames[0].save(out_path, save_all=True, append_images=frames[1:],
               duration=int(1000 / FPS), loop=0, optimize=True)

pygame.quit()

print(f"saved: {out_path}")
print(f"preview: {preview_path}")
print(f"frames: {N_FRAMES}")
