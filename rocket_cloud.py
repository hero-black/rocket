"""3D 火箭点云动画（pygame 点云版，离屏渲染并导出 GIF）

对应你提供的 pygame 点云脚本：圆柱/鼻锥/尾翼/喷口点云 + 透视投影 + 相机推拉动画。
原脚本依赖交互窗口实时播放；这里改用 SDL dummy 驱动离屏渲染逐帧截图，再合成 GIF。
不覆盖此前的 rocket.py / rocket3d.py / rocket3d_orbit.py。
"""

import math
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")   # 无窗口离屏渲染

import numpy as np
import pygame
from PIL import Image

pygame.init()

W, H = 900, 900
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("3D Rocket Point Cloud")
font = pygame.font.Font(None, 26)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
FPS = 24
DURATION = 12.0
N_FRAMES = int(DURATION * FPS)
OUT_SIZE = 480


# ============ 生成火箭点云 ============
def generate_rocket():
    points = []
    normals = []

    R = 12
    BODY_H = 120
    NOSE_H = 40

    # 圆柱体表面
    n_theta = 50
    n_y = 60
    for i in range(n_theta):
        theta = 2 * math.pi * i / n_theta
        for j in range(n_y + 1):
            y = j * BODY_H / n_y
            x = R * math.cos(theta)
            z = R * math.sin(theta)
            points.append((x, y, z))
            normals.append((math.cos(theta), 0, math.sin(theta)))

    # 鼻锥表面
    n_cone = 40
    for i in range(n_theta):
        theta = 2 * math.pi * i / n_theta
        for j in range(1, n_cone + 1):
            t = j / n_cone
            rr = R * (1 - t)
            y = BODY_H + t * NOSE_H
            x = rr * math.cos(theta)
            z = rr * math.sin(theta)
            points.append((x, y, z))
            nrm = math.sqrt(1 + (R / NOSE_H) ** 2)
            normals.append((math.cos(theta) / nrm, (R / NOSE_H) / nrm,
                            math.sin(theta) / nrm))

    # 鼻锥顶点
    points.append((0, BODY_H + NOSE_H, 0))
    normals.append((0, 1, 0))

    # 4 个尾翼
    for k in range(4):
        angle = k * math.pi / 2
        fin_width = 18
        fin_height = 35
        n_w = 12
        n_h = 15
        for i in range(n_w + 1):
            for j in range(n_h + 1):
                r = R + fin_width * i / n_w
                y = fin_height * j / n_h
                x = r * math.cos(angle)
                z = r * math.sin(angle)
                points.append((x, y, z))
                normals.append((math.cos(angle), 0, math.sin(angle)))

    # 喷口（倒锥）
    nozzle_h = 15
    for i in range(n_theta):
        theta = 2 * math.pi * i / n_theta
        for j in range(1, 10):
            t = j / 10
            rr = R * (0.6 + 0.4 * t)
            y = -t * nozzle_h
            x = rr * math.cos(theta)
            z = rr * math.sin(theta)
            points.append((x, y, z))
            normals.append((math.cos(theta), -0.3, math.sin(theta)))

    return np.array(points, dtype=np.float64), np.array(normals, dtype=np.float64)


# ============ 投影函数 ============
def project(points, cam_pos, target, fov):
    cam_pos = np.array(cam_pos, dtype=np.float64)
    target = np.array(target, dtype=np.float64)

    forward = target - cam_pos
    forward = forward / np.linalg.norm(forward)

    world_up = np.array([0, 1, 0], dtype=np.float64)
    if abs(np.dot(forward, world_up)) > 0.99:
        world_up = np.array([0, 0, 1], dtype=np.float64)

    right = np.cross(forward, world_up)
    right = right / np.linalg.norm(right)
    up = np.cross(right, forward)

    d = points - cam_pos
    x_view = d @ right
    y_view = d @ up
    z_view = d @ forward

    valid = z_view > 0.1
    z_safe = np.where(valid, z_view, 1.0)

    screen_x = W / 2 + fov * x_view / z_safe
    screen_y = H / 2 - fov * y_view / z_safe

    return screen_x, screen_y, z_view, valid


# ============ 相机动画 ============
points, normals = generate_rocket()
rocket_height = 120 + 40


def get_camera(t_norm):
    s = t_norm
    s = s * s * (3 - 2 * s)

    angle = -0.4 + 0.8 * s

    cam_y = -40 + (350 - (-40)) * s
    cam_z = 40 + (250 - 40) * s
    cam_x = 60 * math.sin(angle) * (1 - s) * s * 2

    cam_pos = np.array([cam_x, cam_y, cam_z])

    start_target = np.array([0, 40, 0])
    end_target = np.array([0, rocket_height / 2, 0])
    target = start_target + (end_target - start_target) * s

    start_fov = 200
    end_fov = 300
    fov = start_fov + (end_fov - start_fov) * s

    return cam_pos, target, fov


def render(t_norm):
    cam_pos, target, fov = get_camera(t_norm)

    screen.fill((255, 255, 255))

    sx, sy, sz, valid = project(points, cam_pos, target, fov)
    mask = valid & (sx > -50) & (sx < W + 50) & (sy > -50) & (sy < H + 50)

    if mask.sum() > 0:
        z_valid = sz[mask]
        sx_valid = sx[mask]
        sy_valid = sy[mask]

        z_min = z_valid.min()
        z_max = z_valid.max()
        if z_max - z_min > 0.1:
            z_norm = (z_valid - z_min) / (z_max - z_min)
        else:
            z_norm = np.zeros_like(z_valid)

        sizes = np.clip(8.0 / (z_valid / 100 + 1), 1.0, 6.0)

        for i in range(len(sx_valid)):
            x = int(sx_valid[i])
            y = int(sy_valid[i])
            if 0 <= x < W and 0 <= y < H:
                pygame.draw.circle(screen, (0, 0, 0), (x, y), int(sizes[i]))

    info = f"Camera animation: {t_norm * 100:.0f}%" if t_norm < 1.0 else "Press R to replay"
    text = font.render(info, True, (0, 0, 0))
    screen.blit(text, (10, 10))

    return pygame.image.tostring(screen, "RGB")


# ============ 逐帧离屏渲染 ============
frames = []
for idx in range(N_FRAMES):
    raw = render(idx / N_FRAMES)
    img = Image.frombytes("RGB", (W, H), raw)
    img = img.resize((OUT_SIZE, OUT_SIZE), Image.LANCZOS)
    frames.append(img.convert("P", palette=Image.ADAPTIVE, colors=32))

# 取一张中间帧作为预览
preview_path = os.path.join(OUT_DIR, "rocket_cloud_preview.png")
frames[int(N_FRAMES * 0.75)].save(preview_path)

out_path = os.path.join(OUT_DIR, "rocket_cloud.gif")
frames[0].save(out_path, save_all=True, append_images=frames[1:],
               duration=int(1000 / FPS), loop=0, optimize=True)

pygame.quit()

print(f"saved: {out_path}")
print(f"preview: {preview_path}")
print(f"points: {len(points)}, frames: {N_FRAMES}")
