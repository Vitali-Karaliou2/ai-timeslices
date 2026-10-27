"""Рисунок 1 («матрёшка»), компактный вариант: ширина внутреннего прямоугольника (DL)
подогнана под его подпись; внешние — по своим подписям. Единицы рисунка — пункты."""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Ellipse
plt.rcParams["font.family"] = "DejaVu Sans"
out = sys.argv[1]
FS = 11.5          # кегль подписей, pt
PAD = 9            # отступ подписи от левой границы, pt
M = 22             # зазор между вложенными рамками, pt (вмещает кружки б, в, г)
labels = [
    ("Искусственный интеллект (AI), 1955–1956", "#dbe9f6", "#2f6ea5"),
    ("Машинное обучение (ML), 1959 / 1980-е", "#dcefdc", "#3b8a3b"),
    ("Нейронные сети (NN), 1943", "#fbe5cc", "#c96a12"),
    ("Глубокое обучение (DL), 1965 / 2006", "#f6d2d2", "#b02a2a"),
]
# ширины подписей в пунктах
fig0 = plt.figure(dpi=72); r = fig0.canvas.get_renderer()
wid = [fig0.text(0, 0, t, fontsize=FS, fontweight="bold").get_window_extent(r).width for t, *_ in labels]
plt.close(fig0)
dl_w = wid[3] + 2 * PAD                      # внутренний прямоугольник ровно по подписи
W = [dl_w + 2 * M * (3 - i) for i in range(4)]  # AI, ML, NN, DL
W = [max(W[i], wid[i] + 2 * PAD) for i in range(4)]
# вложенность по ширине должна сохраниться: каждая рамка не уже внутренней + 2M
for i in (2, 1, 0):
    W[i] = max(W[i], W[i + 1] + 2 * M)
HEAD = 26          # высота строки подписи
DL_H = 150         # высота внутреннего прямоугольника
H = [DL_H + (HEAD + M / 2) * (3 - i) + M / 2 * (3 - i) for i in range(4)]
fig_w, fig_h = W[0] + 4, H[0] + 4
fig, ax = plt.subplots(figsize=(fig_w / 72, fig_h / 72), dpi=200)
fig.subplots_adjust(0, 0, 1, 1)
x0 = y0 = 2
boxes = []
for i, (t, fc, ec) in enumerate(labels):
    x = x0 + (W[0] - W[i]) / 2 if False else x0 + M * i
    y = y0 + M / 2 * i
    w, h = W[i], H[i]
    boxes.append((x, y, w, h))
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=8", fc=fc, ec=ec, lw=1.6))
    ax.text(x + PAD, y + h - HEAD / 2 - 2, t, fontsize=FS, fontweight="bold", color=ec, va="center")
# генеративный ИИ: овал от середины DL до правой границы AI
dlx, dly, dlw, dlh = boxes[3]
right = boxes[0][0] + boxes[0][2] - 3
left = dlx + dlw * 0.40
cy = dly + dlh * 0.33
ax.add_patch(Ellipse(((left + right) / 2, cy), right - left, 62, fc="#8a5cc9", alpha=0.18, ec="#6a3fa8", lw=2, ls="--"))
tx = dlx + dlw * 0.66
ax.text(tx, cy + 12, "Генеративный ИИ", fontsize=12, fontweight="bold", color="#5a2f98", ha="center")
ax.text(tx, cy - 2, "(Generative AI)", fontsize=10.5, color="#5a2f98", ha="center")
def mark(x, y, s):
    ax.add_patch(plt.Circle((x, y), 7.5, fc="white", ec="#6a3fa8", lw=1.4, zorder=3))
    ax.text(x, y, s, fontsize=10.5, ha="center", va="center", color="#5a2f98", fontweight="bold", zorder=4)
mark(tx, cy - 18, "а")
for k, s in enumerate("бвг"):           # в зазорах между правыми границами DL|NN, NN|ML, ML|AI
    inner = boxes[3 - k]; outer = boxes[2 - k]
    mark((inner[0] + inner[2] + outer[0] + outer[2]) / 2, cy, s)
ax.set_xlim(0, fig_w); ax.set_ylim(0, fig_h); ax.set_aspect("equal"); ax.axis("off")
fig.savefig(out, facecolor="white")
print(out, [round(w) for w in W], round(fig_w), round(fig_h))
