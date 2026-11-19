"""Line charts for the housing report, rendered by matplotlib as inline SVG.

Design rules (shared across every chart in the report):
- Fixed color per geography, never cycled: ZIP = blue, state = orange,
  US = aqua. The same entity keeps the same color in every chart.
- 2px lines, faint grid, one y-axis per chart.
- A legend plus a direct label at the end of each line, so identity never
  depends on color alone (the aqua is low-contrast on white).
"""

import io
from datetime import date

import matplotlib

matplotlib.use("svg")  # no GUI window; render straight to SVG

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

# Categorical slots 1-3 of the reference palette (validated colorblind-safe
# as a set of three)
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]

TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
SURFACE = "#ffffff"

plt.rcParams.update({
    "svg.fonttype": "none",  # keep text as text, so the page font applies
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "Arial", "DejaVu Sans"],
    "font.size": 8.5,
    "axes.edgecolor": GRID,
    "axes.labelcolor": TEXT_SECONDARY,
    "xtick.color": TEXT_SECONDARY,
    "ytick.color": TEXT_SECONDARY,
})


def money_k(value, _pos=None):
    """Axis label: $350k, $1.2M."""
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs(value) >= 10_000:
        return f"${value / 1_000:.0f}k"
    return f"${value:,.0f}"


def percent(value, _pos=None):
    return f"{value:.1f}%"


FORMATTERS = {"money": money_k, "percent": percent}


def line_chart(series, y_format="money", width_in=7.0, height_in=2.1):
    """Return an SVG string for a line chart.

    series: list of dicts with keys label, short_label, dates (list of
            date), values (list of float), and slot (0, 1, or 2): the
            entity's fixed color slot, so a geography keeps its color even
            when another series is missing from the chart.
    y_format: "money" or "percent".
    """
    fig, ax = plt.subplots(figsize=(width_in, height_in), facecolor=SURFACE)
    fmt = FORMATTERS[y_format]

    ends = []  # (x, y, label text) for the direct labels
    for s in series:
        if not s["dates"]:
            continue
        color = SERIES_COLORS[s["slot"]]
        ax.plot(s["dates"], s["values"], color=color, linewidth=2 * 0.75,  # 2px at 96 dpi
                label=s["label"], solid_capstyle="round")
        # Marker at the line end in the series color
        ax.plot(s["dates"][-1], s["values"][-1], "o", markersize=4, color=color,
                markeredgecolor=SURFACE, markeredgewidth=1)
        ends.append((s["dates"][-1], s["values"][-1], f"{s['short_label']} {fmt(s['values'][-1])}"))

    ax.yaxis.set_major_formatter(FuncFormatter(fmt))
    # Fit the x-axis to the data, so no empty year appears at either end
    all_dates = [d for s in series for d in s["dates"]]
    if all_dates:
        ax.set_xlim(min(all_dates), max(all_dates))
    ax.xaxis.set_major_locator(mdates.YearLocator(base=2 if _span_years(series) > 6 else 1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)
    if len(series) > 1:
        ax.legend(loc="upper left", bbox_to_anchor=(0, 1.16), ncol=len(series),
                  frameon=False, fontsize=8, handlelength=1.6)

    # Leave room on the right for the end labels
    fig.subplots_adjust(left=0.08, right=0.80, top=0.86, bottom=0.12)
    _place_end_labels(fig, ax, ends)

    buffer = io.StringIO()
    fig.savefig(buffer, format="svg")
    plt.close(fig)
    svg = buffer.getvalue()
    # Drop the XML prolog and DOCTYPE so the SVG can sit inside HTML
    return svg[svg.index("<svg"):]


def _place_end_labels(fig, ax, ends, min_gap_pt=11):
    """Write each line's end label (in text ink, not the series color),
    nudging labels apart vertically so lines that finish close together
    don't print on top of each other."""
    if not ends:
        return
    ax.autoscale_view()
    to_points = 72 / fig.dpi  # display pixels -> points
    # Each label's natural height on the page, in points
    placed = sorted(
        (ax.transData.transform((mdates.date2num(x), y))[1] * to_points, x, y, text)
        for x, y, text in ends
    )
    adjusted = []
    for natural, x, y, text in placed:
        target = natural if not adjusted else max(natural, adjusted[-1][0] + min_gap_pt)
        adjusted.append((target, natural, x, y, text))
    for target, natural, x, y, text in adjusted:
        ax.annotate(
            text, xy=(x, y), xytext=(6, target - natural), textcoords="offset points",
            va="center", fontsize=8, color=TEXT_PRIMARY, annotation_clip=False,
        )


def _span_years(series):
    all_dates = [d for s in series for d in s["dates"]]
    if not all_dates:
        return 0
    first: date = min(all_dates)
    last: date = max(all_dates)
    return (last - first).days / 365.25
