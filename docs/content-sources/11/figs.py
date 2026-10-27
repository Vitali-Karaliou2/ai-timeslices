import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Ellipse

plt.rcParams["font.family"] = "DejaVu Sans"

# ---------- Рисунок 1: вложенные области + Generative AI ----------
fig, ax = plt.subplots(figsize=(10, 5.6), dpi=200)
boxes = [  # (x0, y0, x1, y1, fill, edge, title)
    (0.0, 0.0, 14.0, 7.6, "#dbe9f6", "#2f6ea5", "Искусственный интеллект (AI), 1955–1956"),
    (0.5, 0.45, 12.6, 6.7, "#dcefdc", "#3b8a3b", "Машинное обучение (ML), 1959 / 1980-е"),
    (1.0, 0.9, 11.2, 5.8, "#fbe5cc", "#c96a12", "Нейронные сети (NN), 1943"),
    (1.5, 1.35, 9.8, 4.9, "#f6d2d2", "#b02a2a", "Глубокое обучение (DL), 1965 / 2006"),
]
for x0, y0, x1, y1, fc, ec, title in boxes:
    ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0,
                                boxstyle="round,pad=0,rounding_size=0.35",
                                fc=fc, ec=ec, lw=1.6))
    ax.text(x0 + 0.3, y1 - 0.42, title, fontsize=11.5, fontweight="bold", color=ec, va="center")

ell = Ellipse((10.0, 2.55), 7.6, 2.5, fc="#8a5cc9", alpha=0.18, ec="#6a3fa8", lw=2, ls="--")
ax.add_patch(ell)
ax.text(8.0, 2.95, "Генеративный ИИ", fontsize=12, fontweight="bold", color="#5a2f98", ha="center")
ax.text(8.0, 2.5, "(Generative AI)", fontsize=10.5, color="#5a2f98", ha="center")
for x, y, s in [(8.0, 1.85, "а"), (10.5, 2.55, "б"), (11.9, 2.55, "в"), (13.25, 2.55, "г")]:
    ax.add_patch(plt.Circle((x, y), 0.27, fc="white", ec="#6a3fa8", lw=1.4))
    ax.text(x, y, s, fontsize=11, ha="center", va="center", color="#5a2f98", fontweight="bold")

ax.set_xlim(-0.1, 14.1); ax.set_ylim(-0.1, 7.7); ax.set_aspect("equal"); ax.axis("off")
fig.savefig("fig1_nested.png", bbox_inches="tight", facecolor="white")

# ---------- Рисунок 2: когда появились направления ----------
fig, ax = plt.subplots(figsize=(11, 4.7), dpi=200)
Y0, Y1 = 1940, 2027
rows = [  # label, color, solid_from, dashed_from, milestones
    ("Нейронные сети", "#c96a12", 1943, None,
     [(1943, "нейрон М.–П."), (1957, "перцептрон"), (1969, "«Perceptrons»"), (1986, "backprop")]),
    ("Искусственный\nинтеллект", "#2f6ea5", 1956, 1955,
     [(1956, "Дартмут"), (1997, "Deep Blue")]),
    ("Машинное\nобучение", "#3b8a3b", 1980, 1959,
     [(1959, "термин (Самуэль)"), (1980, "отд. область"), (1992, "SVM")]),
    ("Глубокое\nобучение", "#b02a2a", 2006, 1965,
     [(1965, "Ивахненко–Лапа"), (2006, "DBN"), (2012, "AlexNet"), (2017, "Transformer")]),
    ("Генеративный\nИИ", "#6a3fa8", 2014, 1948,
     [(1948, "Шеннон: n-граммы"), (2014, "GAN"), (2022, "ChatGPT")]),
]
for i, (label, color, solid, dashed, ms) in enumerate(rows):
    y = 4.6 - i * 1.0
    if dashed:
        ax.plot([dashed, solid], [y, y], color=color, lw=3, ls=(0, (2, 2)), alpha=0.7)
    ax.plot([solid, 2026], [y, y], color=color, lw=6, solid_capstyle="butt")
    ax.text(Y0 - 1, y, label, ha="right", va="center", fontsize=10, color=color, fontweight="bold")
    for k, (yr, txt) in enumerate(ms):
        ax.plot([yr], [y], marker="o", ms=7, mfc="white", mec=color, mew=2, zorder=3)
        dy = 0.3 if k % 2 == 0 else -0.32
        ax.text(yr, y + dy, f"{yr} {txt}", ha="center", va="center", fontsize=8.2, color="#222")

ax.set_xlim(Y0, Y1); ax.set_ylim(0.2, 5.15)
ax.set_xticks(range(1940, 2030, 10)); ax.tick_params(axis="x", labelsize=9)
ax.set_yticks([])
for s in ("left", "right", "top"):
    ax.spines[s].set_visible(False)
ax.grid(axis="x", color="#ddd", lw=0.6)
fig.savefig("fig2_timeline.png", bbox_inches="tight", facecolor="white")
