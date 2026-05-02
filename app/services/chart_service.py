import io
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import seaborn as sns

from app.services.data_service import get_cleaned_data


def generate_chart_image(files, include_fail_data, channels) -> tuple[bytes, str]:
    full_df, unique_cps, reports, _summary = get_cleaned_data(
        files, include_fail_data, channels
    )
    if full_df is None:
        raise ValueError("所选文件无有效数据可以用于绘图")

    sources = full_df["Source"].unique()
    n_sources = len(sources)
    n_cp = len(unique_cps)

    if n_sources > 10:
        sources = sources[:10]
        full_df = full_df[full_df["Source"].isin(sources)]
        n_sources = 10

    base_box_width = 0.108
    min_box_width = 0.05
    cp_margin = 0.072

    if n_sources == 1:
        single_box_width = base_box_width
        group_width_physical = single_box_width
        sns_gap = 0.0
    else:
        single_box_width = base_box_width - (base_box_width - min_box_width) * (n_sources - 1) / 9.0
        sns_gap = 0.1
        element_physical_width = single_box_width / (1 - sns_gap)
        group_width_physical = n_sources * element_physical_width

    cp_total_width = group_width_physical + cp_margin
    sns_width = group_width_physical / cp_total_width

    calculated_width = max(8.0, cp_total_width * n_cp)
    font_calc_width = min(calculated_width, 20.0)
    dynamic_fontsize = max(8, min(12, int(font_calc_width / 1.2)))
    title_fontsize = max(16, min(26, int(font_calc_width * 1.8)))

    if n_sources <= 4:
        box_lw, median_lw, whisker_lw = 1.5, 1.0, 0.6
    else:
        box_lw, median_lw, whisker_lw = 1.0, 0.8, 0.4

    custom_palette = [
        "#0000FF",
        "#FF0000",
        "#00CC00",
        "#FF00FF",
        "#FF9900",
        "#00FFFF",
        "#9900CC",
        "#FF007F",
        "#00FF00",
        "#008080",
    ]
    if n_sources == 2:
        custom_palette = ["#0000FF", "#FF0000"]

    plt.rcParams["font.sans-serif"] = ["Arial", "sans-serif"]
    channels = channels or ["Tx_LC", "Tx_MC", "Tx_HC"]
    channels = [ch for ch in channels if ch in full_df["Channel"].unique()]
    fig, axes = plt.subplots(len(channels), 1, figsize=(calculated_width, 6.5 * len(channels)), sharex=True)
    if len(channels) == 1:
        axes = [axes]
    plt.subplots_adjust(hspace=0.0)

    g_min, g_max = full_df["Delta"].min(), full_df["Delta"].max()
    padding = (g_max - g_min) * 0.05 if (g_max - g_min) != 0 else 1
    y_min, y_max = math.floor(g_min - padding), math.ceil(g_max + padding)
    y_min, y_max = min(y_min, -6), max(y_max, 0)
    if y_min % 2 != 0:
        y_min -= 1
    if y_max % 2 != 0:
        y_max += 1

    for i, ch in enumerate(channels):
        ax = axes[i]
        ch_data = full_df[full_df["Channel"] == ch]
        sns.boxplot(
            data=ch_data,
            x="CheckPoint",
            y="Delta",
            hue="Source",
            ax=ax,
            palette=custom_palette[:n_sources],
            showfliers=False,
            dodge=True,
            width=sns_width,
            gap=sns_gap,
            linewidth=box_lw,
            whis=[0, 100],
            showcaps=False,
            boxprops={"edgecolor": "none"},
            medianprops={"color": "white", "linewidth": median_lw},
            fliersize=0,
        )

        all_children = ax.get_children()
        rects_info = []
        for child in all_children:
            if isinstance(child, patches.PathPatch):
                path = child.get_path()
                vertices = path.vertices
                if len(vertices) > 0:
                    rx = (vertices[:, 0].max() + vertices[:, 0].min()) / 2
                    rects_info.append({"x": rx, "color": child.get_facecolor()})

        for child in all_children:
            if isinstance(child, plt.Line2D):
                xdata, ydata = child.get_xdata(), child.get_ydata()
                if len(xdata) == 2 and abs(xdata[0] - xdata[1]) < 0.001 and ydata[0] != ydata[1]:
                    lx = xdata[0]
                    for r_info in rects_info:
                        if abs(lx - r_info["x"]) < 0.1:
                            child.set_color(r_info["color"])
                            child.set_linewidth(whisker_lw)
                            child.set_zorder(5)
                            break

        ax.axhline(y=-6, color="#FF0000", linestyle="--", linewidth=1.5, zorder=10)
        ax.axhline(y=0, color="gray", linewidth=0.5, alpha=0.5)
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color("black")
            spine.set_linewidth(1.0)
        ax.set_ylim(y_min, y_max)
        ticks = [t for t in range(int(y_min), int(y_max) + 1, 2)]
        ax.set_yticks(ticks)
        ax.set_yticklabels([str(t) for t in ticks])
        ax.set_ylabel(ch, fontsize=14, fontweight="bold", labelpad=15)
        ax.grid(False)
        ax.set_facecolor("white")
        if i == 0:
            ax.set_title("Tx power drop", fontsize=title_fontsize, fontweight="bold", pad=20, loc="left")
            ax.legend(
                title="",
                bbox_to_anchor=(1.0, 1.02),
                loc="lower right",
                frameon=False,
                fontsize=dynamic_fontsize,
                ncol=1,
                labelspacing=0.2,
                handletextpad=0.5,
            )
        elif ax.get_legend():
            ax.get_legend().remove()

    plt.xlabel("CP", fontsize=14, fontweight="bold", labelpad=15)
    plt.xticks(rotation=45, ha="right", fontsize=dynamic_fontsize)

    unique_sources = list(full_df["Source"].unique())
    short_sources = ["-".join(s.split("-")[:3]) for s in unique_sources]
    build_suffix = short_sources[0] if len(short_sources) == 1 else "_vs_".join(short_sources)

    output_name = f"OTA_JMP_{build_suffix}.png"
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)

    return buf.getvalue(), output_name
