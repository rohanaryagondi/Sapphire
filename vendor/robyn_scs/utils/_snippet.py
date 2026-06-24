if MODE == 'batch':
    DISPLAY_ORDER = ['Excitatory', 'Inhibitory', 'Ambiguous',
                     'No validated efferent connections']
    from utils.quiver_style import QUIVER_NEURON_COLORS
    colors = [QUIVER_NEURON_COLORS[l] for l in DISPLAY_ORDER]

    for R in all_fov_results:
        counts = (R['neuron_tier']['consensus_type']
                  .map(DISPLAY_NAMES)
                  .value_counts()
                  .reindex(DISPLAY_ORDER, fill_value=0))

        mask  = counts.values > 0
        sizes = counts.values[mask]
        lbls  = [l for l, m in zip(DISPLAY_ORDER, mask) if m]
        clrs  = [c for c, m in zip(colors, mask) if m]

        fig, ax = plt.subplots()
        patches, texts, autotexts = ax.pie(
            sizes, labels=lbls, autopct='%1.1f%%',
            colors=clrs, startangle=140)
        for text, color in zip(texts, clrs):
            text.set_color(color)
            text.set_fontweight('bold')
        ax.set_title(R['fov'])
        ax.axis('equal')

        fov_dir = os.path.join(OUTPUT_DIR, R['fov'])
        os.makedirs(fov_dir, exist_ok=True)
        for ext in ['svg', 'png']:
            plt.savefig(os.path.join(fov_dir, f'pie_chart.{ext}'), bbox_inches='tight')
        plt.close()
