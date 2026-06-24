% SCS_BrowseTraces.m
% =====================================================================
% Browse all neuron traces from a single FOV in paged 5x5 grids.
%
% Page 1..N : Stim neurons  — smoothed trace + yellow stim markers
% Page N+1..: Non-stim neurons — smoothed trace only
%
% Press any key (in the figure window) to advance pages.
% Neuron number (T#) shown in each subplot title — note candidates
% then use SCS_PlotConnection.m to inspect pairs.
%
% Robyn St. Laurent, May 2026.
% =====================================================================

clearvars; close all;

% ── Configuration ────────────────────────────────────────────────────────
FOV_DIR  = 'R:\QNP\2026_QNP\2026-05-12_JenniferGrooms_FireflyOne\PlateNumber_1\v16_traces';
OUT_STEM = '\FOV_0006_2026-05-12_13_14_10_483-FireflyOne-12g';   % <-- edit this

FS       = 500;   % Hz
SMOOTH_S = 0.01;  % Gaussian sigma in seconds

STRIP_HEIGHT = 1.0;   % normalised units per strip (gap between baselines)
TRACE_AMP    = 0.45;  % how tall each trace is within its strip (0–0.5)

% ── Colours ──────────────────────────────────────────────────────────────
c_stim_tr = [0.35 0.75 1.00];
c_post_tr = [1.00 0.60 0.25];
c_stim_mk = [0.95 0.95 0.30];
bg        = [0.10 0.10 0.13];
ax_bg     = [0.10 0.10 0.13];

% ── Load CSVs ────────────────────────────────────────────────────────────
csv1   = fullfile(FOV_DIR, [OUT_STEM '_stim_part1.csv']);
csv2   = fullfile(FOV_DIR, [OUT_STEM '_stim_part2.csv']);
meta_f = fullfile(FOV_DIR, [OUT_STEM '_stim_meta.json']);

fprintf('Loading traces...\n');
T1 = readtable(csv1);
T2 = readtable(csv2);
T  = [T1; T2];

n_samp   = height(T);
t_axis   = (0:n_samp-1) / FS;
all_cols = T.Properties.VariableNames;
n_src    = numel(all_cols);

% ── Load metadata ────────────────────────────────────────────────────────
fprintf('Loading metadata...\n');
fid  = fopen(meta_f, 'r');
raw  = fread(fid, '*char')';
fclose(fid);
meta = jsondecode(raw);

split_pt = meta.stim_split_local;
stim_ids = meta.stim_mask_sources(:)';
all_ids  = cellfun(@(c) str2double(c(2:end)), all_cols);
post_ids = setdiff(all_ids, stim_ids);

fprintf('Stim neurons: %d   Non-stim: %d   Total: %d\n', ...
        numel(stim_ids), numel(post_ids), n_src);

% ── Smooth all traces ─────────────────────────────────────────────────────
fprintf('Smoothing %d traces (kernel = %.0f ms)...\n', n_src, SMOOTH_S*1000);
traces = zeros(n_samp, n_src);
for s = 1:n_src
    traces(:, s) = smooth_nan(T.(all_cols{s}), SMOOTH_S, FS);
end
fprintf('Done.\n\n');

% ── Plot ─────────────────────────────────────────────────────────────────
plot_stack(stim_ids,  traces, all_ids, t_axis, meta, split_pt, FS, ...
           STRIP_HEIGHT, TRACE_AMP, c_stim_tr, c_stim_mk, bg, ax_bg, ...
           true,  'STIM neurons');

plot_stack(post_ids, traces, all_ids, t_axis, meta, split_pt, FS, ...
           STRIP_HEIGHT, TRACE_AMP, c_post_tr, c_stim_mk, bg, ax_bg, ...
           false, 'NON-STIM neurons (post candidates)');

fprintf('Done.\n');

% =====================================================================
% Local functions
% =====================================================================

function plot_stack(ids, traces, all_ids, t_axis, meta, split_pt, fs, ...
                    strip_h, amp, trace_color, stim_color, bg, ax_bg, ...
                    show_stim, fig_title)

    n = numel(ids);
    if n == 0
        fprintf('No neurons for: %s\n', fig_title);
        return;
    end

    fig_h = max(400, n * 14);   % ~14px per strip, min 400
    figure('Name', fig_title, ...
           'Position', [80 60 1600 min(fig_h, 900)], ...
           'Color', bg);

    ax = axes('Position', [0.08 0.06 0.90 0.88]);
    hold on;
    set(ax, 'Color', ax_bg, 'XColor', 'w', 'YColor', 'w', ...
        'TickDir', 'out', 'FontSize', 8, 'YDir', 'reverse');

    % Global stim times for the vertical lines that span the full figure
    global_stim_t = [];
    if show_stim
        p1 = meta.stim_frames_part1(:);
        p2 = meta.stim_frames_part2(:) + split_pt;
        global_stim_t = [p1; p2] / fs;
    end

    ytick_pos    = zeros(1, n);
    ytick_labels = cell(1, n);

    for si = 1:n
        src_id  = ids(si);
        col_idx = find(all_ids == src_id, 1);
        tr      = traces(:, col_idx);

        % Normalise trace to [-amp, +amp]
        valid = tr(~isnan(tr));
        if isempty(valid) || range(valid) == 0
            tr_norm = zeros(size(tr));
        else
            tr_norm = (tr - mean(valid, 'omitnan')) / (0.5 * range(valid));
            tr_norm = tr_norm * amp;
        end

        baseline = (si - 1) * strip_h;
        plot(t_axis, baseline + tr_norm, ...
             'Color', trace_color, 'LineWidth', 0.6);

        ytick_pos(si)    = baseline;
        ytick_labels{si} = sprintf('T%d', src_id);
    end

    % Stim event lines spanning full y range
    if show_stim && ~isempty(global_stim_t)
        y_lo = -amp;
        y_hi = (n-1) * strip_h + amp;
        for k = 1:numel(global_stim_t)
            plot([global_stim_t(k) global_stim_t(k)], [y_lo y_hi], ...
                 'Color', [stim_color, 0.4], 'LineWidth', 0.8);
        end
    end

    xlim([t_axis(1) t_axis(end)]);
    ylim([-amp, (n-1)*strip_h + amp]);
    set(ax, 'YTick', ytick_pos, 'YTickLabel', ytick_labels, ...
        'YDir', 'normal', 'FontSize', 7);
    xlabel('Time (s)', 'Color', 'w', 'FontSize', 10);
    title(fig_title, 'Color', 'w', 'FontSize', 12, 'FontWeight', 'bold');
end

function st = get_stim_times(meta, src_id, split_pt, fs)
    pre_field = sprintf('T%d', src_id);
    if isfield(meta, 'stim_frames_per_source') && ...
       isfield(meta.stim_frames_per_source, pre_field)
        sf = meta.stim_frames_per_source.(pre_field);
        p1 = sf.part1(:);
        p2 = sf.part2(:) + split_pt;
        st = [p1; p2] / fs;
    else
        p1 = meta.stim_frames_part1(:);
        p2 = meta.stim_frames_part2(:) + split_pt;
        st = [p1; p2] / fs;
    end
end

function out = smooth_nan(x, sigma_s, fs)
    x        = x(:);
    nan_mask = isnan(x);
    if any(nan_mask)
        idx      = (1:numel(x))';
        x_interp = x;
        x_interp(nan_mask) = interp1(idx(~nan_mask), x(~nan_mask), ...
                                     idx(nan_mask), 'linear', 'extrap');
    else
        x_interp = x;
    end
    sigma_samp = sigma_s * fs;
    half_w     = ceil(3 * sigma_samp);
    k_idx      = (-half_w:half_w)';
    kernel     = exp(-0.5 * (k_idx / sigma_samp).^2);
    kernel     = kernel / sum(kernel);
    out        = conv(x_interp, kernel, 'same');
    out(nan_mask) = NaN;
    out = out(:);
end
