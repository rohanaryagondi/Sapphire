"""
Quiver Bioscience — matplotlib/seaborn style module.
Import once at the top of any notebook or script to apply the Quiver look globally.

Usage:
    import utils.quiver_style                          # auto-applies on import
    # or
    from utils.quiver_style import apply_quiver_style, QUIVER_COLORS, QUIVER_CYCLE
    apply_quiver_style()
"""

import matplotlib as mpl
from matplotlib import font_manager
from cycler import cycler

# ── Palette ──────────────────────────────────────────────────────────────────

QUIVER_COLORS = {
    "purple":      "#9C02FA",   # primary brand color
    "red":         "#F51D3F",   # gradient end / strong accent
    "dark_purple": "#7300BF",   # deep accent
    "magenta":     "#C20CA9",   # mid-gradient
    "lilac":       "#CAA1FF",   # soft highlight
    "hot_pink":    "#FF85FF",   # bright accent
    "salmon":      "#F9788B",   # warm accent
    "soft_pink":   "#FEEBFF",   # light background tint
    "navy":        "#0D1130",   # dark background
    "lavender_bg": "#F5F0FF",   # light background
}

# Ordered cycle for categorical plots — adjacent colors have good contrast
QUIVER_CYCLE = [
    "#9C02FA",  # purple  ← Excitatory (bluish purple)
    "#F51D3F",  # red     ← Inhibitory (stop-sign red)
    "#C20CA9",  # magenta ← Ambiguous
    "#CAA1FF",  # lilac
    "#F9788B",  # salmon
    "#FF85FF",  # hot pink
    "#7300BF",  # dark purple
]

# Semantic neuron-type colors — use for exc/inh/ambiguous labeling
QUIVER_NEURON_COLORS = {
    "Excitatory":                        "#9C02FA",  # bluish purple
    "Inhibitory":                        "#F51D3F",  # stop-sign red
    "Ambiguous":                         "#C20CA9",  # magenta
    "No validated efferent connections": "#888888",  # neutral gray
}

# ── Font ─────────────────────────────────────────────────────────────────────

_available_fonts = {f.name for f in font_manager.fontManager.ttflist}
QUIVER_FONT = "Poppins" if "Poppins" in _available_fonts else "DejaVu Sans"

# ── rcParams ─────────────────────────────────────────────────────────────────

QUIVER_RC = {
    # Figure
    "figure.figsize":       (8, 5),
    "figure.dpi":           150,
    "figure.facecolor":     "white",
    "figure.edgecolor":     "white",

    # Axes
    "axes.facecolor":       "white",
    "axes.edgecolor":       "#333333",
    "axes.linewidth":       0.8,
    "axes.spines.top":      False,
    "axes.spines.right":    False,
    "axes.prop_cycle":      cycler("color", QUIVER_CYCLE),
    "axes.titlesize":       12,
    "axes.titleweight":     "bold",
    "axes.labelsize":       10,
    "axes.labelcolor":      "#000000",

    # Ticks
    "xtick.major.size":     4,
    "xtick.minor.size":     2,
    "xtick.major.width":    0.8,
    "xtick.labelsize":      9,
    "xtick.color":          "#333333",
    "ytick.major.size":     4,
    "ytick.minor.size":     2,
    "ytick.major.width":    0.8,
    "ytick.labelsize":      9,
    "ytick.color":          "#333333",

    # Lines & markers
    "lines.linewidth":      1.5,
    "lines.markersize":     5,

    # Legend
    "legend.fontsize":      9,
    "legend.framealpha":    0.85,
    "legend.edgecolor":     "#CCCCCC",

    # Save
    "savefig.dpi":          300,
    "savefig.bbox":         "tight",
    "savefig.facecolor":    "white",

    # Font (Poppins preferred, graceful fallbacks)
    "font.family":          "sans-serif",
    "font.sans-serif":      ["Poppins", "DejaVu Sans", "Arial", "Helvetica", "sans-serif"],
    "font.size":            10,
}


# ── Functions ─────────────────────────────────────────────────────────────────

def apply_quiver_style() -> None:
    """Apply Quiver rcParams globally. Call once at the top of a notebook or script."""
    mpl.rcParams.update(QUIVER_RC)


def quiver_diverging_cmap():
    """Diverging colormap: Quiver purple → white → Quiver red."""
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list(
        "quiver_div", [QUIVER_COLORS["purple"], "white", QUIVER_COLORS["red"]]
    )


def quiver_sequential_cmap():
    """Sequential colormap: white → Quiver magenta → Quiver purple."""
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list(
        "quiver_seq", ["white", QUIVER_COLORS["magenta"], QUIVER_COLORS["purple"]]
    )


def neuron_colors(labels):
    """
    Return a list of colors for a list of neuron-type label strings.
    Falls back to QUIVER_CYCLE for any label not in QUIVER_NEURON_COLORS.

    Example:
        colors = neuron_colors(['Excitatory', 'Inhibitory', 'Ambiguous'])
    """
    cycle = QUIVER_CYCLE
    cycle_idx = 0
    result = []
    for label in labels:
        if label in QUIVER_NEURON_COLORS:
            result.append(QUIVER_NEURON_COLORS[label])
        else:
            result.append(cycle[cycle_idx % len(cycle)])
            cycle_idx += 1
    return result


# ── Auto-apply on import ──────────────────────────────────────────────────────
apply_quiver_style()
