import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, FFMpegWriter, PillowWriter
from matplotlib.patches import Polygon, Rectangle, Circle, Ellipse

# 中文显示
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ============================================================
# 参数
# ============================================================
rng = np.random.default_rng(7)

FPS = 30
DT = 1.0 / FPS
DURATION = 16.0                 # 动画总长（秒）
N_FRAMES = int(DURATION * FPS)
COUNTDOWN = 3.0                 # 倒计时秒数
GROUND_TOP = -5.0               # 地面世界坐标 y

XLIM = (-10, 10)
YLIM = (-6, 14)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# 画布
# ============================================================
fig, ax = plt.subplots(figsize=(6, 9))
fig.patch.set_facecolor('#050810')
ax.set_facecolor('#050810')
ax.set_xlim(*XLIM)
ax.set_ylim(*YLIM)
ax.set_aspect('equal')
ax.axis('off')
ax.set_position([0, 0, 1, 1])

# ============================================================
# 星空
# ============================================================
N_STARS = 150
star_x = rng.uniform(*XLIM, N_STARS)
star_sy = rng.uniform(YLIM[0], YLIM[1], N_STARS)
star_sizes = rng.uniform(1, 14, N_STARS)
stars = ax.scatter(star_x, star_sy, s=star_sizes, c='white',
                   alpha=0.85, zorder=1, edgecolors='none')

# ============================================================
# 云层
# ============================================================
clouds = []
for _ in range(6):
    cx = rng.uniform(-9, 9)
    cy = rng.uniform(-5, 9)
    cw = rng.uniform(2.5, 4.5)
    ch = rng.uniform(0.4, 0.8)
    p = Ellipse((cx, cy), cw, ch, fc='white', alpha=0.10, lw=0, zorder=2)
    ax.add_patch(p)
    clouds.append({'patch': p, 'x': cx, 'sy': cy})

# ============================================================
# 地面
# ============================================================
ground = Rectangle((-10, GROUND_TOP - 8), 20, 8,
                   fc='#1e2430', ec='#3a4454', lw=2, zorder=3)
ax.add_patch(ground)

# ============================================================
# 火箭部件（坐标相对喷口，喷口为 y=0）
# ============================================================
body = Polygon(np.zeros((4, 2)), closed=True, fc='#e9ecf2', ec='#8b93a3', lw=1.6, zorder=10)
nose = Polygon(np.zeros((3, 2)), closed=True, fc='#e2483d', ec='#9c2a20', lw=1.6, zorder=11)
fin_l = Polygon(np.zeros((3, 2)), closed=True, fc='#e2483d', ec='#9c2a20', lw=1.6, zorder=9)
fin_r = Polygon(np.zeros((3, 2)), closed=True, fc='#e2483d', ec='#9c2a20', lw=1.6, zorder=9)
window = Circle((0, 0), 0.28, fc='#63c7ea', ec='#2b7f9c', lw=1.6, zorder=12)
flame = Polygon(np.zeros((3, 2)), closed=True, fc='#ffb020', ec='#ff6a00', lw=1.2, zorder=8)

for p in (body, nose, fin_l, fin_r, window, flame):
    ax.add_patch(p)


def place_rocket(nozzle_sy):
    """按喷口屏幕 y 坐标重绘火箭各部件"""
    body.set_xy([[-0.55, nozzle_sy + 0.2], [0.55, nozzle_sy + 0.2],
                 [0.55, nozzle_sy + 2.9], [-0.55, nozzle_sy + 2.9]])
    nose.set_xy([[-0.55, nozzle_sy + 2.9], [0.55, nozzle_sy + 2.9],
                 [0.0, nozzle_sy + 4.2]])
    fin_l.set_xy([[-0.55, nozzle_sy + 0.2], [-1.35, nozzle_sy - 0.55],
                  [-0.55, nozzle_sy + 1.1]])
    fin_r.set_xy([[0.55, nozzle_sy + 0.2], [1.35, nozzle_sy - 0.55],
                  [0.55, nozzle_sy + 1.1]])
    window.set_center((0.0, nozzle_sy + 2.15))


# ============================================================
# 烟雾散点
# ============================================================
smoke_scatter = ax.scatter([], [], s=[], c=[], zorder=6, edgecolors='none')

# ============================================================
# 文字
# ============================================================
hud = ax.text(-9.5, 13.6, '', ha='left', va='top',
              fontsize=11, color='#8fd3ff', family='monospace', zorder=20)
countdown_text = ax.text(0, 6.5, '', ha='center', va='center',
                         fontsize=64, color='white', weight='bold', zorder=21)

# ============================================================
# 状态
# ============================================================
t = 0.0
h = GROUND_TOP      # 喷口世界高度
v = 0.0             # 世界速度
cam = 0.0           # 摄像机偏移
prev_cam = 0.0
smoke = []


def animate(i):
    global t, h, v, cam, prev_cam, smoke

    if i == 0:
        t, h, v, cam, prev_cam = 0.0, GROUND_TOP, 0.0, 0.0, 0.0
        smoke = []

    t = i * DT

    # ---------------- 物理 ----------------
    thrusting = t >= COUNTDOWN
    if thrusting:
        tt = t - COUNTDOWN
        accel = 0.6 + 0.06 * tt
        v += accel * DT
        h += v * DT

    # ---------------- 摄像机 ----------------
    cam = max(cam, max(0.0, h + 2.0))
    dcam = cam - prev_cam
    prev_cam = cam

    nozzle_sy = h - cam

    # ---------------- 火箭 ----------------
    place_rocket(nozzle_sy)

    if thrusting:
        flame_len = 0.9 + rng.uniform(0.0, 0.7)
        flame.set_xy([[-0.38, nozzle_sy + 0.25],
                      [0.38, nozzle_sy + 0.25],
                      [0.0, nozzle_sy - flame_len]])
        flame.set_facecolor('#ffb020' if rng.random() < 0.6 else '#ffd35c')
        flame.set_visible(True)
    else:
        flame.set_visible(False)

    # ---------------- 烟雾 ----------------
    if thrusting and rng.random() < 0.95:
        for _ in range(2):
            smoke.append({
                'x': rng.normal(0, 0.18),
                'y': h + rng.normal(0, 0.15),
                'vx': rng.normal(0, 1.1),
                'vy': rng.normal(-1.2, 1.0),
                'life': 0.0,
                'max_life': rng.uniform(0.7, 1.6),
                'size': rng.uniform(0.6, 1.4),
            })

    alive = []
    for p in smoke:
        p['life'] += DT
        if p['life'] >= p['max_life']:
            continue
        p['x'] += p['vx'] * DT
        p['y'] += p['vy'] * DT
        p['vy'] -= 0.6 * DT
        p['vx'] *= 0.99
        alive.append(p)
    smoke = alive

    if smoke:
        xs = np.array([p['x'] for p in smoke])
        ys = np.array([p['y'] - cam for p in smoke])
        frac = np.array([1 - p['life'] / p['max_life'] for p in smoke])
        ss = 90 * frac * np.array([p['size'] for p in smoke]) + 8
        rgba = np.zeros((len(smoke), 4))
        rgba[:, :3] = 0.86
        rgba[:, 3] = 0.55 * frac
        smoke_scatter.set_offsets(np.column_stack([xs, ys]))
        smoke_scatter.set_sizes(ss)
        smoke_scatter.set_facecolors(rgba)
        smoke_scatter.set_visible(True)
    else:
        smoke_scatter.set_visible(False)

    # ---------------- 星空视差 ----------------
    star_sy[:] -= dcam * 0.12
    while True:
        below = star_sy < YLIM[0] - 0.5
        if not below.any():
            break
        n = int(below.sum())
        star_sy[below] += (YLIM[1] - YLIM[0] + 2.0)
        star_x[below] = rng.uniform(*XLIM, n)
    stars.set_offsets(np.column_stack([star_x, star_sy]))

    # ---------------- 云视差 ----------------
    for c in clouds:
        c['sy'] -= dcam * 0.45
        if c['sy'] < YLIM[0] - 2:
            c['sy'] += (YLIM[1] - YLIM[0] + 6)
            c['x'] = rng.uniform(*XLIM)
        c['patch'].set_center((c['x'], c['sy']))

    # ---------------- 地面 ----------------
    ground.set_y(GROUND_TOP - cam - 8)

    # ---------------- 文字 ----------------
    alt = max(0.0, h - GROUND_TOP) * 10.0
    speed = v * 10.0
    hud.set_text(
        f"ALT  {alt:8.1f} m\n"
        f"VEL  {speed:8.1f} m/s\n"
        f"T    {t:8.2f} s"
    )

    if t < COUNTDOWN:
        countdown_text.set_text(str(int(np.ceil(COUNTDOWN - t))))
        countdown_text.set_color('#ffffff')
        countdown_text.set_alpha(0.9)
    elif t < COUNTDOWN + 0.6:
        countdown_text.set_text("点火")
        countdown_text.set_color('#ff7a45')
        countdown_text.set_alpha(1.0 - (t - COUNTDOWN) / 0.6)
    else:
        countdown_text.set_text("")

    return (body, nose, fin_l, fin_r, window, flame, smoke_scatter,
            stars, ground, hud, countdown_text, *[c['patch'] for c in clouds])


ani = FuncAnimation(fig, animate, frames=N_FRAMES,
                    interval=1000 / FPS, blit=False)

# ============================================================
# 导出视频（优先 MP4，缺少 ffmpeg 时退化为 GIF）
# ============================================================
if FFMpegWriter.isAvailable():
    out_path = os.path.join(OUT_DIR, "rocket_launch.mp4")
    writer = FFMpegWriter(fps=FPS, bitrate=2400)
else:
    out_path = os.path.join(OUT_DIR, "rocket_launch.gif")
    writer = PillowWriter(fps=FPS)

ani.save(out_path, writer=writer, dpi=100)
plt.close(fig)

print(f"saved: {out_path}")
