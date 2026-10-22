"""3D 火箭发射动画（环绕相机版，matplotlib 3D 复刻）

对应你提供的 vpython 增强版脚本：环绕相机、地面网格、加强筋、扭转尾翼、3D 烟雾。
vpython 依赖浏览器 WebGL，无法无头导出视频，故用 matplotlib 3D 复刻并导出 GIF/MP4。
不覆盖此前的 rocket.py 与 rocket3d.py。
"""

import os
from math import cos, degrees, radians, sin

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, FFMpegWriter, PillowWriter
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
rng = np.random.default_rng(11)

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
ROCKET_Z0 = 1.0            # 喷口初始高度（与 vpython nozzle_world.y = 1.0 一致）

ORBIT_SPEED = 0.18         # 相机环绕角速度 rad/s
AZIM0 = -90.0              # 初始方位角（度）

COL_BODY = '#eceef4'
COL_RIB = '#bfc3cc'
COL_RED = '#e2483d'
COL_NOZZLE = '#47474d'
COL_GROUND = '#1a202c'
COL_GRID = '#38425a'
COL_PAD = '#474c59'
COL_TOWER = '#616170'
COL_FLAME_OUT = '#ff8000'
COL_FLAME_IN = '#ffeba8'

# ============================================================
# 几何辅助
# ============================================================
def cyl(cx, cy, z0, z1, r, n=24):
    th = np.linspace(0.0, 2 * np.pi, n + 1)
    xs = cx + r * np.cos(th)
    ys = cy + r * np.sin(th)
    return [[(xs[i], ys[i], z0), (xs[i + 1], ys[i + 1], z0),
             (xs[i + 1], ys[i + 1], z1), (xs[i], ys[i], z1)] for i in range(n)]


def cone(cx, cy, z0, h, r, n=24):
    th = np.linspace(0.0, 2 * np.pi, n + 1)
    xs = cx + r * np.cos(th)
    ys = cy + r * np.sin(th)
    return [[(xs[i], ys[i], z0), (xs[i + 1], ys[i + 1], z0),
             (cx, cy, z0 + h)] for i in range(n)]


def disc(cx, cy, cz, r, n=24):
    th = np.linspace(0.0, 2 * np.pi, n + 1)
    return [[(cx + r * np.cos(t), cy + r * np.sin(t), cz) for t in th]]


def box(cx, cy, cz, sx, sy, sz):
    x0, x1 = cx - sx / 2, cx + sx / 2
    y0, y1 = cy - sy / 2, cy + sy / 2
    z0, z1 = cz - sz / 2, cz + sz / 2
    p = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    idx = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4),
           (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return [[p[i] for i in f] for f in idx]


def shift(faces, dz):
    return [[(x, y, z + dz) for (x, y, z) in f] for f in faces]


def add(ax, faces, color, alpha=1.0):
    if not faces:
        return
    pc = Poly3DCollection(faces, facecolors=color, edgecolors='none', linewidths=0)
    pc.set_alpha(alpha)
    ax.add_collection3d(pc)


# ============================================================
# 静态场景
# ============================================================
GROUND_FACES = [[(-45, -45, -1.0), (45, -45, -1.0),
                 (45, 45, -1.0), (-45, 45, -1.0)]]
GRID_LINES = []
for g in range(-42, 43, 6):
    GRID_LINES.append(([g, g], [-42, 42], [-0.99, -0.99]))
    GRID_LINES.append(([-42, 42], [g, g], [-0.99, -0.99]))

PAD_FACES = cyl(0, 0, -0.95, 0.35, 4.5, n=32) + disc(0, 0, 0.37, 4.2, n=32)

TOWER_FACES = box(-4.5, 0, 5.0, 0.9, 0.9, 12.0)
for yy in [2, 4, 6, 8, 10, 12]:
    TOWER_FACES += box(-3.5, 0, yy, 2.0, 0.35, 0.18)
    TOWER_FACES += box(-3.5, 0, yy, 0.35, 2.0, 0.18)

PIPE_FACES = box(-1.6, 0, 1.0, 1.2, 0.22, 0.22)
CLAMP_FACES = box(-1.6, 0, 2.5, 0.7, 2.5, 0.5) + box(1.6, 0, 2.5, 0.7, 2.5, 0.5)

# 星空（背景板，随相机反向旋转以保持稳定）
N_STARS = 320
star_x = rng.uniform(-14, 14, N_STARS)
star_y = rng.uniform(-14, 14, N_STARS)
star_z = rng.uniform(1, 23, N_STARS)
star_s = rng.uniform(1.5, 12, N_STARS)

# ============================================================
# 画布
# ============================================================
fig = plt.figure(figsize=(8.0, 7.6), facecolor='#050810')
ax = fig.add_axes([0, 0, 1, 1], projection='3d', facecolor='#050810')

hud_text = fig.text(0.035, 0.96, '', ha='left', va='top', fontsize=11,
                    color='#8fd3ff', family='monospace')
count_text = fig.text(0.5, 0.72, '', ha='center', va='center',
                      fontsize=44, color='white', weight='bold')

# ============================================================
# 状态
# ============================================================
state = {'z': ROCKET_Z0, 'v': 0.0, 'smoke': []}


def draw_frame(i):
    st = state
    if i == 0:
        st['z'], st['v'], st['smoke'] = ROCKET_Z0, 0.0, []

    t = i * DT

    # ---------------- 相机环绕 ----------------
    azim = AZIM0 + degrees(ORBIT_SPEED * t)
    delta = radians(azim - AZIM0)   # 用于星空背景补偿

    # ---------------- 物理 ----------------
    thrusting = t >= COUNTDOWN
    if thrusting:
        tt = t - COUNTDOWN
        thrust = 26.0 + 6.0 * (1.0 - tt / BURN) if tt < BURN else 0.0
        st['v'] += (thrust - G) * DT
        st['z'] += st['v'] * DT
        if st['z'] < ROCKET_Z0:
            st['z'], st['v'] = ROCKET_Z0, 0.0
        shake = 0.0
    else:
        thrust = 0.0
        shake = 0.03 * (1 + COUNTDOWN - t)

    rz = st['z']
    cam = max(0.0, rz - 5.0)

    # ---------------- 重建场景 ----------------
    ax.clear()
    ax.set_facecolor('#050810')
    ax.set_axis_off()
    ax.set_autoscale_on(False)   # 禁止 draw 时按数据范围重算视野
    ax.set_xlim(-10, 10)
    ax.set_ylim(-10, 10)
    ax.set_zlim(-4, 20)
    ax.set_box_aspect((1, 1, 1.2))
    ax.set_proj_type('ortho')
    ax.view_init(elev=12, azim=azim)

    # 地面与网格（透视深度线索）
    add(ax, shift(GROUND_FACES, -cam), COL_GROUND, 1.0)
    for lx, ly, lz in GRID_LINES:
        ax.plot(lx, ly, [z - cam for z in lz], color=COL_GRID, linewidth=0.9)

    # 发射台 / 塔架 / 管线 / 夹钳
    add(ax, shift(PAD_FACES, -cam), COL_PAD, 1.0)
    add(ax, shift(TOWER_FACES, -cam), COL_TOWER, 1.0)
    add(ax, shift(PIPE_FACES, -cam), '#8c7340', 1.0)
    if not thrusting:
        add(ax, shift(CLAMP_FACES, -cam), '#80808c', 1.0)

    # 星空：绕 z 轴反向旋转，保持背景稳定；高度做缓慢视差
    c, s = np.cos(-delta), np.sin(-delta)
    sx = star_x * c - star_y * s
    sy = star_x * s + star_y * c
    sz = (star_z - cam * 0.08 - 1.0) % 22.0 + 1.0
    ax.scatter(sx, sy, sz, s=star_s, c='white', alpha=0.85,
               depthshade=False, edgecolors='none')

    # ---------------- 火箭 ----------------
    xoff = rng.uniform(-shake, shake) if shake else 0.0
    zc = rz - cam
    add(ax, cyl(xoff, 0, zc, zc + 6.0, 0.85), COL_BODY, 1.0)

    # 4 条加强筋（曲面感）
    for ang in (0, 90, 180, 270):
        a = radians(ang)
        add(ax, cyl(xoff + 0.87 * cos(a), 0.87 * sin(a),
                    zc + 0.1, zc + 5.9, 0.06, n=8), COL_RIB, 1.0)

    # 环形装饰
    add(ax, cyl(xoff, 0, zc + 0.25, zc + 0.50, 0.90), COL_RED, 1.0)
    add(ax, cyl(xoff, 0, zc + 5.45, zc + 5.70, 0.90), COL_RED, 1.0)

    # 鼻锥 / 喷口
    add(ax, cone(xoff, 0, zc + 6.0, 2.3, 0.85), COL_RED, 1.0)
    add(ax, cone(xoff, 0, zc, -0.5, 0.70), COL_NOZZLE, 1.0)

    # 舷窗（朝相机初始方向 -y）
    add(ax, disc(xoff, -0.88, zc + 4.3, 0.38), '#59bff2', 1.0)

    # 尾翼 4 片
    fins = (box(xoff + 1.95, 0, zc + 0.85, 2.2, 0.10, 1.8)
            + box(xoff - 1.95, 0, zc + 0.85, 2.2, 0.10, 1.8)
            + box(xoff, 1.95, zc + 0.85, 0.10, 2.2, 1.8)
            + box(xoff, -1.95, zc + 0.85, 0.10, 2.2, 1.8))
    add(ax, fins, COL_RED, 1.0)

    # ---------------- 尾焰 ----------------
    if thrust > 0:
        fl = rng.uniform(0.75, 1.35)
        add(ax, cone(xoff, 0, zc, -3.2 * fl, 0.75 * rng.uniform(0.9, 1.1)),
            COL_FLAME_OUT, 0.8)
        add(ax, cone(xoff, 0, zc, -1.8 * fl, 0.42 * rng.uniform(0.9, 1.1)),
            COL_FLAME_IN, 0.95)

    # ---------------- 3D 烟雾 ----------------
    if thrust > 0 and (rz - ROCKET_Z0) < 20 and len(st['smoke']) < 120:
        for _ in range(2):
            if len(st['smoke']) >= 120:
                break
            st['smoke'].append({
                'x': xoff + rng.uniform(-0.6, 0.6),
                'y': rng.uniform(-0.6, 0.6),
                'z': rz + rng.uniform(-0.4, 0.4),
                'vx': rng.uniform(-3.0, 3.0),
                'vy': rng.uniform(-3.0, 3.0),
                'vz': rng.uniform(-2.0, 0.5),
                'life': 0.0,
                'max_life': rng.uniform(1.8, 3.5),
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
        px = np.array([p['x'] for p in st['smoke']])
        py = np.array([p['y'] for p in st['smoke']])
        pz = np.array([p['z'] for p in st['smoke']]) - cam
        frac = np.array([1 - p['life'] / p['max_life'] for p in st['smoke']])
        ss = 700 * frac * np.array([p['r'] for p in st['smoke']]) + 8
        cols = np.zeros((len(st['smoke']), 4))
        cols[:, :3] = 0.68
        cols[:, 3] = 0.5 * frac
        ax.scatter(px, py, pz, s=ss, c=cols, depthshade=False, edgecolors='none')

    # ---------------- HUD / 倒计时 ----------------
    hud_text.set_text(
        f"ALT  {max(0.0, rz - ROCKET_Z0) * 10:8.1f} m    "
        f"VEL {st['v'] * 10:8.1f} m/s    T {t:6.2f} s"
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

    # 视野必须在所有 3D 对象加入之后设置：add_collection3d 会触发自动缩放，
    # 若提前设置会被后续对象的数据范围覆盖，导致镜头过远、主体过小。
    ax.set_xlim(-10, 10)
    ax.set_ylim(-10, 10)
    ax.set_zlim(-4, 20)
    ax.set_box_aspect((1, 1, 1.2))
    ax.set_proj_type('ortho')
    ax.view_init(elev=12, azim=azim)

    return []


ani = FuncAnimation(fig, draw_frame, frames=N_FRAMES,
                    interval=1000 / FPS, blit=False)

# 中间帧预览（便于快速检视构图）
draw_frame(int(8.0 * FPS))
preview_path = os.path.join(OUT_DIR, "rocket3d_orbit_preview.png")
fig.savefig(preview_path, dpi=80, facecolor=fig.get_facecolor())

# ============================================================
# 导出视频（优先 MP4，缺少 ffmpeg 时退化为 GIF）
# ============================================================
if FFMpegWriter.isAvailable():
    out_path = os.path.join(OUT_DIR, "rocket_launch_3d_orbit.mp4")
    writer = FFMpegWriter(fps=FPS, bitrate=2800)
else:
    out_path = os.path.join(OUT_DIR, "rocket_launch_3d_orbit.gif")
    writer = PillowWriter(fps=FPS)

ani.save(out_path, writer=writer, dpi=90)
plt.close(fig)

print(f"saved: {out_path}")
print(f"preview: {preview_path}")
