"""3D 火箭发射动画（matplotlib 3D 版，可离线渲染为视频文件）

说明：vpython 依赖浏览器 WebGL 实时渲染，无法在无头环境直接导出视频文件。
本脚本用 matplotlib 3D 复刻同样的场景（发射台、塔架、星空、尾焰、烟雾、HUD），
并导出为 GIF / MP4。不覆盖此前的 rocket.py。
"""

import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, FFMpegWriter, PillowWriter
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
rng = np.random.default_rng(7)

# ============================================================
# 参数
# ============================================================
FPS = 20
DT = 1.0 / FPS
DURATION = 13.0
N_FRAMES = int(DURATION * FPS)

COUNTDOWN = 3.0
BURN = 6.5
G = 9.8
ROCKET_Z0 = 0.7          # 火箭喷口初始高度（发射台顶面之上）

COL_BODY = '#eceef4'
COL_RED = '#e2483d'
COL_NOZZLE = '#47474d'
COL_GROUND = '#1a202c'
COL_PAD = '#454a59'
COL_TOWER = '#5c5c66'
COL_FLAME_OUT = '#ff8000'
COL_FLAME_IN = '#ffeba8'

# ============================================================
# 几何辅助
# ============================================================
def cyl(cx, cy, z0, z1, r, n=20):
    """竖直圆柱侧面"""
    th = np.linspace(0.0, 2 * np.pi, n + 1)
    xs = cx + r * np.cos(th)
    ys = cy + r * np.sin(th)
    return [[(xs[i], ys[i], z0), (xs[i + 1], ys[i + 1], z0),
             (xs[i + 1], ys[i + 1], z1), (xs[i], ys[i], z1)] for i in range(n)]


def cone(cx, cy, z0, h, r, n=20):
    """圆锥侧面，底面在 z0，顶点在 z0 + h"""
    th = np.linspace(0.0, 2 * np.pi, n + 1)
    xs = cx + r * np.cos(th)
    ys = cy + r * np.sin(th)
    return [[(xs[i], ys[i], z0), (xs[i + 1], ys[i + 1], z0),
             (cx, cy, z0 + h)] for i in range(n)]


def disc_xz(cx, cy, cz, r, n=20):
    """xz 平面上的圆盘（用于台面 / 舷窗）"""
    th = np.linspace(0.0, 2 * np.pi, n + 1)
    return [[(cx + r * np.cos(t), cy, cz + r * np.sin(t)) for t in th]]


def box(cx, cy, cz, sx, sy, sz):
    """以中心点定义的长方体"""
    x0, x1 = cx - sx / 2, cx + sx / 2
    y0, y1 = cy - sy / 2, cy + sy / 2
    z0, z1 = cz - sz / 2, cz + sz / 2
    p = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    idx = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4),
           (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return [[p[i] for i in f] for f in idx]


def shift(faces, dz):
    """整体沿 z 平移"""
    return [[(x, y, z + dz) for (x, y, z) in f] for f in faces]


def add(ax, faces, color, alpha=1.0):
    if not faces:
        return
    pc = Poly3DCollection(faces, facecolors=color, edgecolors='none', linewidths=0)
    pc.set_alpha(alpha)
    ax.add_collection3d(pc)


# ============================================================
# 静态场景（世界坐标，绘制时按 cam 平移）
# ============================================================
GROUND_FACES = [[(-60, -60, -0.5), (60, -60, -0.5),
                 (60, 60, -0.5), (-60, 60, -0.5)]]
GRID_LINES = []
for gx in range(-20, 21, 4):
    GRID_LINES.append(([gx, gx], [-30, 30], [-0.49, -0.49]))
for gy in range(-20, 21, 4):
    GRID_LINES.append(([-30, 30], [gy, gy], [-0.49, -0.49]))

PAD_FACES = cyl(0, 0, -0.5, 0.1, 4.5, n=28) + disc_xz(0, 0, 0.12, 4.2, n=28)

TOWER_FACES = box(-4.5, 0, 5.5, 0.9, 0.9, 12.0)
for yy in [2, 4, 6, 8, 10, 12]:
    TOWER_FACES += box(-3.5, 0, yy, 2.0, 0.35, 0.18)
    TOWER_FACES += box(-3.5, 0, yy, 0.35, 2.0, 0.18)

PIPE_FACES = box(-1.6, 0, 1.0, 1.2, 0.22, 0.22)
CLAMP_FACES = box(-1.6, 0, 2.5, 0.7, 2.5, 0.5) + box(1.6, 0, 2.5, 0.7, 2.5, 0.5)

# 星空
N_STARS = 280
star_x = rng.uniform(-14, 14, N_STARS)
star_y = rng.uniform(6, 14, N_STARS)
star_z = rng.uniform(2, 23, N_STARS)
star_s = rng.uniform(2, 16, N_STARS)

# ============================================================
# 画布
# ============================================================
fig = plt.figure(figsize=(7.5, 8.0), facecolor='#050810')
ax = fig.add_axes([0, 0, 1, 1], projection='3d', facecolor='#050810')

hud_text = fig.text(0.04, 0.96, '', ha='left', va='top', fontsize=11,
                    color='#8fd3ff', family='monospace')
count_text = fig.text(0.5, 0.55, '', ha='center', va='center',
                      fontsize=56, color='white', weight='bold')

# ============================================================
# 动画状态
# ============================================================
state = {'t': 0.0, 'z': ROCKET_Z0, 'v': 0.0, 'smoke': []}


def draw_frame(i):
    st = state
    if i == 0:
        st['t'], st['z'], st['v'], st['smoke'] = 0.0, ROCKET_Z0, 0.0, []

    t = i * DT
    st['t'] = t

    # ---------------- 物理 ----------------
    thrusting = t >= COUNTDOWN
    if thrusting:
        tt = t - COUNTDOWN
        thrust = 26.0 + 6.0 * (1.0 - tt / BURN) if tt < BURN else 0.0
    else:
        thrust = 0.0

    if thrusting:
        st['v'] += (thrust - G) * DT
        st['z'] += st['v'] * DT
        if st['z'] < ROCKET_Z0:
            st['z'], st['v'] = ROCKET_Z0, 0.0

    rz = st['z']
    cam = max(0.0, rz - 6.0)

    # ---------------- 清空并重建场景 ----------------
    ax.clear()
    ax.set_facecolor('#050810')
    ax.set_axis_off()
    ax.set_xlim(-12, 12)
    ax.set_ylim(-15, 15)
    ax.set_zlim(-3, 24)
    ax.set_box_aspect((24, 30, 27))
    ax.view_init(elev=9, azim=-90)

    # 地面与网格
    add(ax, shift(GROUND_FACES, -cam), COL_GROUND, 1.0)
    for lx, ly, lz in GRID_LINES:
        ax.plot(lx, ly, [z - cam for z in lz], color='#2b3444', linewidth=0.8)

    # 发射台 / 塔架 / 管线 / 夹钳
    add(ax, shift(PAD_FACES, -cam), COL_PAD, 1.0)
    add(ax, shift(TOWER_FACES, -cam), COL_TOWER, 1.0)
    add(ax, shift(PIPE_FACES, -cam), '#8c7340', 1.0)
    if not thrusting:
        add(ax, shift(CLAMP_FACES, -cam), '#80808c', 1.0)

    # 星空（随相机轻微视差循环）
    sz = (star_z - cam * 0.15 - 2.0) % 21.0 + 2.0
    ax.scatter(star_x, star_y, sz, s=star_s, c='white',
               alpha=0.85, depthshade=False, edgecolors='none')

    # ---------------- 火箭 ----------------
    zc = rz - cam
    add(ax, cyl(0, 0, zc, zc + 6.0, 0.85), COL_BODY, 1.0)
    add(ax, cyl(0, 0, zc + 0.25, zc + 0.50, 0.88), COL_RED, 1.0)
    add(ax, cyl(0, 0, zc + 5.45, zc + 5.70, 0.88), COL_RED, 1.0)
    add(ax, cone(0, 0, zc + 6.0, 2.3, 0.85), COL_RED, 1.0)
    add(ax, cone(0, 0, zc, -0.5, 0.70), COL_NOZZLE, 1.0)
    add(ax, disc_xz(0, -0.88, zc + 4.3, 0.38), '#59bff2', 1.0)

    fins = (box(1.95, 0, zc + 0.85, 2.2, 0.08, 1.8)
            + box(-1.95, 0, zc + 0.85, 2.2, 0.08, 1.8)
            + box(0, 1.95, zc + 0.85, 0.08, 2.2, 1.8)
            + box(0, -1.95, zc + 0.85, 0.08, 2.2, 1.8))
    add(ax, fins, COL_RED, 1.0)

    # ---------------- 尾焰 ----------------
    if thrust > 0:
        fl = rng.uniform(0.75, 1.35)
        add(ax, cone(0, 0, zc, -3.2 * fl, 0.75 * rng.uniform(0.9, 1.1)),
            COL_FLAME_OUT, 0.85)
        add(ax, cone(0, 0, zc, -1.8 * fl, 0.42 * rng.uniform(0.9, 1.1)),
            COL_FLAME_IN, 0.95)

    # ---------------- 烟雾 ----------------
    if thrust > 0 and (rz - ROCKET_Z0) < 15 and len(st['smoke']) < 90:
        for _ in range(2):
            if len(st['smoke']) >= 90:
                break
            st['smoke'].append({
                'x': rng.uniform(-0.6, 0.6),
                'y': rng.uniform(-0.6, 0.6),
                'z': rz + rng.uniform(-0.4, 0.4),
                'vx': rng.uniform(-2.5, 2.5),
                'vy': rng.uniform(-2.5, 2.5),
                'vz': rng.uniform(-1.5, 0.5),
                'life': 0.0,
                'max_life': rng.uniform(1.5, 3.0),
                'r': rng.uniform(0.25, 0.55),
            })

    alive = []
    for p in st['smoke']:
        p['life'] += DT
        if p['life'] >= p['max_life']:
            continue
        p['x'] += p['vx'] * DT
        p['y'] += p['vy'] * DT
        p['z'] += p['vz'] * DT
        p['vz'] += 0.3 * DT
        p['r'] *= (1 + 0.4 * DT)
        alive.append(p)
    st['smoke'] = alive

    if st['smoke']:
        xs = np.array([p['x'] for p in st['smoke']])
        ys = np.array([p['y'] for p in st['smoke']])
        zs = np.array([p['z'] for p in st['smoke']]) - cam
        frac = np.array([1 - p['life'] / p['max_life'] for p in st['smoke']])
        ss = 700 * frac * np.array([p['r'] for p in st['smoke']]) + 8
        cols = np.zeros((len(st['smoke']), 4))
        cols[:, :3] = 0.68
        cols[:, 3] = 0.55 * frac
        ax.scatter(xs, ys, zs, s=ss, c=cols, depthshade=False, edgecolors='none')

    # ---------------- HUD / 倒计时 ----------------
    alt = max(0.0, rz - ROCKET_Z0) * 10.0
    hud_text.set_text(
        f"ALT  {alt:8.1f} m    VEL {st['v'] * 10:8.1f} m/s    T {t:6.2f} s"
    )

    if t < COUNTDOWN:
        count_text.set_text(str(int(np.ceil(COUNTDOWN - t))))
        count_text.set_color('#ffffff')
        count_text.set_alpha(0.9)
    elif t < COUNTDOWN + 1.0:
        count_text.set_text("点火!")
        count_text.set_color('#ff9a4a')
        count_text.set_alpha(1.0 - (t - COUNTDOWN) / 1.0)
    else:
        count_text.set_text("")

    return []


ani = FuncAnimation(fig, draw_frame, frames=N_FRAMES,
                    interval=1000 / FPS, blit=False)

# ============================================================
# 导出视频（优先 MP4，缺少 ffmpeg 时退化为 GIF）
# ============================================================
if FFMpegWriter.isAvailable():
    out_path = os.path.join(OUT_DIR, "rocket_launch_3d.mp4")
    writer = FFMpegWriter(fps=FPS, bitrate=2600)
else:
    out_path = os.path.join(OUT_DIR, "rocket_launch_3d.gif")
    writer = PillowWriter(fps=FPS)

ani.save(out_path, writer=writer, dpi=90)
plt.close(fig)

print(f"saved: {out_path}")
