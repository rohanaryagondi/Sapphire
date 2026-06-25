% SCS_PlotConnection.m
% =====================================================================
% Plot pre/post-synaptic traces from SCS stim CSVs and optionally
% play them as a synchronized scrolling movie.
%
% Usage:
%   1. Set FOV_DIR to the v16_traces folder (or wherever your CSVs live).
%   2. Set OUT_STEM to the base name shared by the CSV/JSON files for
%      your chosen FOV (everything before _stim_part1.csv etc).
%   3. Set PRE_ID and POST_ID to the neuron (source) numbers you want.
%   4. Run. The static plot appears first; type 'y' in the Command
%      Window to launch the scrolling movie.
%
% Robyn St. Laurent, May 2026.
% =====================================================================

clearvars; close all;

% ── Configuration ────────────────────────────────────────────────────────
FOV_DIR  = 'R:\QNP\2026_QNP\2026-05-12_JenniferGrooms_FireflyOne\PlateNumber_2\v16_traces';

% Base name: everything before _stim_part1.csv / _stim_meta.json
OUT_STEM = '\FOV_0008_2026-05-12_15_55_03_914-FireflyOne-12g';   % <-- edit this

PRE_ID   = 1;   % <-- presynaptic neuron number
POST_ID  = 53;    % <-- postsynaptic neuron number

CONNECTION_TYPE = 'excitatory';  % label only — 'excitatory' | 'inhibitory'

FS = 500;  % Hz

% ── Smoothing ─────────────────────────────────────────────────────────────
% Gaussian kernel width in seconds. 0.15 s (75 samples) is a good starting
% point for calcium-like signals at 500 Hz. Increase for more smoothing.
SMOOTH_S = 0.001;   % seconds  (try 0.05–0.3)

% Movie settings
MOVIE_WINDOW_S  = 20;    % seconds of trace visible at once in the movie
MOVIE_STEP_S    = 0.2; % seconds advanced per frame (~40 fps)
MOVIE_PAUSE_S   = 0.04; % pause between frames (tune for your machine speed)

% ── Load traces (concatenate part1 + part2) ───────────────────────────────
csv1 = fullfile(FOV_DIR, [OUT_STEM '_stim_part1.csv']);
csv2 = fullfile(FOV_DIR, [OUT_STEM '_stim_part2.csv']);
meta_f = fullfile(FOV_DIR, [OUT_STEM '_stim_meta.json']);

fprintf('Loading traces...\n');
T1 = readtable(csv1);
T2 = readtable(csv2);
T  = [T1; T2];   % full stim block

% Column names are T1, T2, ... TN
col_pre  = sprintf('T%d', PRE_ID);
col_post = sprintf('T%d', POST_ID);

if ~ismember(col_pre, T.Properties.VariableNames)
    error('Column %s not found. Available: %s', col_pre, ...
          strjoin(T.Properties.VariableNames, ', '));
end
if ~ismember(col_post, T.Properties.VariableNames)
    error('Column %s not found.', col_post);
end

trace_pre  = T.(col_pre);
trace_post = T.(col_post);
n_samp     = length(trace_pre);
t_axis     = (0:n_samp-1) / FS;   % seconds

% ── NaN-safe Gaussian smoothing ───────────────────────────────────────────
fprintf('Smoothing traces (kernel = %.0f ms)...\n', SMOOTH_S*1000);
trace_pre  = smooth_nan(trace_pre,  SMOOTH_S, FS);
trace_post = smooth_nan(trace_post, SMOOTH_S, FS);

% ── Load stim metadata ────────────────────────────────────────────────────
fprintf('Loading metadata...\n');
fid  = fopen(meta_f, 'r');
raw  = fread(fid, '*char')';
fclose(fid);
meta = jsondecode(raw);

% Stim frames for the presynaptic neuron (local to part1 / part2)
split_pt = meta.stim_split_local;   % where part1 ends (in samples)
stim_n   = meta.stim_n_samples;

stim_frames_abs = [];   % absolute sample indices across concatenated block

pre_field = sprintf('T%d', PRE_ID);
if isfield(meta, 'stim_frames_per_source') && ...
   isfield(meta.stim_frames_per_source, pre_field)
    sf = meta.stim_frames_per_source.(pre_field);
    p1 = sf.part1(:);
    p2 = sf.part2(:) + split_pt;   % remap part2 back to absolute
    stim_frames_abs = [p1; p2];
else
    % Fall back to global stim frames
    p1 = meta.stim_frames_part1(:);
    p2 = meta.stim_frames_part2(:) + split_pt;
    stim_frames_abs = [p1; p2];
    fprintf('  [INFO] No per-source stim frames found for T%d — using global frames.\n', PRE_ID);
end

stim_times = stim_frames_abs / FS;   % convert to seconds

% ── Static Plot ───────────────────────────────────────────────────────────
fprintf('\nPlotting static traces...\n');

fig_static = figure('Name', sprintf('Connection: T%d → T%d (%s)', ...
    PRE_ID, POST_ID, CONNECTION_TYPE), ...
    'Position', [100 100 1400 600], ...
    'Color', [0.12 0.12 0.15]);

% Colour scheme
c_pre  = [0.35 0.75 1.00];   % blue  — presynaptic
c_post = [1.00 0.60 0.25];   % orange — postsynaptic
c_stim = [0.95 0.95 0.30];   % yellow — stim markers
bg     = [0.12 0.12 0.15];
ax_bg  = [0.18 0.18 0.22];

% ── Pre trace ────────────────────────────────────────────────────────────
ax1 = subplot(2,1,1);
plot(t_axis, trace_pre, 'Color', c_pre, 'LineWidth', 0.8);
hold on;
y_lim = ylim;
for k = 1:numel(stim_times)
    xline(stim_times(k), 'Color', [c_stim, 0.6], 'LineWidth', 1.2);
end
ylabel('\DeltaF/F', 'Color', 'w');
title(sprintf('PRE  — neuron T%d', PRE_ID), 'Color', 'w', 'FontSize', 12);
set(ax1, 'Color', ax_bg, 'XColor', 'w', 'YColor', 'w', ...
    'GridColor', [0.4 0.4 0.4], 'GridAlpha', 0.3, 'XGrid', 'on');
xlim([t_axis(1) t_axis(end)]);

% ── Post trace ───────────────────────────────────────────────────────────
ax2 = subplot(2,1,2);
plot(t_axis, trace_post, 'Color', c_post, 'LineWidth', 0.8);
hold on;
for k = 1:numel(stim_times)
    xline(stim_times(k), 'Color', [c_stim, 0.6], 'LineWidth', 1.2);
end
xlabel('Time (s)', 'Color', 'w');
ylabel('\DeltaF/F', 'Color', 'w');
title(sprintf('POST — neuron T%d  |  connection: %s', POST_ID, CONNECTION_TYPE), ...
    'Color', 'w', 'FontSize', 12);
set(ax2, 'Color', ax_bg, 'XColor', 'w', 'YColor', 'w', ...
    'GridColor', [0.4 0.4 0.4], 'GridAlpha', 0.3, 'XGrid', 'on');
xlim([t_axis(1) t_axis(end)]);

linkaxes([ax1 ax2], 'x');

set(gcf, 'Color', bg);
sgtitle(sprintf('SCS Single-Cell Stim  |  T%d → T%d  (%s)  |  stim events: %d', ...
    PRE_ID, POST_ID, CONNECTION_TYPE, numel(stim_times)), ...
    'Color', 'w', 'FontSize', 13, 'FontWeight', 'bold');

fprintf('Static plot ready.\n');
fprintf('Stim events found for T%d: %d\n', PRE_ID, numel(stim_times));

% ── Movie player ─────────────────────────────────────────────────────────
answer = input('\nLaunch scrolling movie? (y/n): ', 's');
if ~strcmpi(strtrim(answer), 'y')
    fprintf('Done.\n');
    return;
end

win_samp  = round(MOVIE_WINDOW_S * FS);
step_samp = round(MOVIE_STEP_S   * FS);
n_frames  = floor((n_samp - win_samp) / step_samp);

fig_movie = figure('Name', sprintf('Movie: T%d → T%d', PRE_ID, POST_ID), ...
    'Position', [150 150 1200 560], ...
    'Color', bg, 'KeyPressFcn', @(src,evt) setappdata(src,'stop',true));
setappdata(fig_movie, 'stop', false);

ma1 = subplot(2,1,1);
ma2 = subplot(2,1,2);

% Pre-compute y-limits from full traces for stable axes
yl_pre  = [min(trace_pre)  - 0.05*range(trace_pre),  ...
           max(trace_pre)  + 0.05*range(trace_pre)];
yl_post = [min(trace_post) - 0.05*range(trace_post), ...
           max(trace_post) + 0.05*range(trace_post)];
if diff(yl_pre)  == 0; yl_pre  = yl_pre  + [-1 1]; end
if diff(yl_post) == 0; yl_post = yl_post + [-1 1]; end

fprintf('\nScrolling movie running — press any key in the figure window to stop.\n');
fprintf('Frame 0 / %d\n', n_frames);

for fr = 0:n_frames
    if ~ishandle(fig_movie) || getappdata(fig_movie, 'stop')
        fprintf('Movie stopped at frame %d.\n', fr);
        break;
    end

    lo = fr * step_samp + 1;
    hi = lo + win_samp - 1;
    hi = min(hi, n_samp);

    t_win  = t_axis(lo:hi);
    p_win  = trace_pre(lo:hi);
    q_win  = trace_post(lo:hi);

    % Stim events in window
    in_win = stim_times(stim_times >= t_win(1) & stim_times <= t_win(end));

    % Pre
    axes(ma1); %#ok<LAXES>
    cla;
    plot(t_win, p_win, 'Color', c_pre, 'LineWidth', 1);
    hold on;
    for k = 1:numel(in_win)
        xline(in_win(k), 'Color', [c_stim, 0.7], 'LineWidth', 1.5);
    end
    ylim(yl_pre);
    xlim([t_win(1) t_win(end)]);
    ylabel('\DeltaF/F', 'Color', 'w');
    title(sprintf('PRE  T%d      t = %.2f s', PRE_ID, t_win(1)), ...
        'Color', 'w', 'FontSize', 11);
    set(ma1, 'Color', ax_bg, 'XColor', 'w', 'YColor', 'w');

    % Post
    axes(ma2); %#ok<LAXES>
    cla;
    plot(t_win, q_win, 'Color', c_post, 'LineWidth', 1);
    hold on;
    for k = 1:numel(in_win)
        xline(in_win(k), 'Color', [c_stim, 0.7], 'LineWidth', 1.5);
    end
    ylim(yl_post);
    xlim([t_win(1) t_win(end)]);
    xlabel('Time (s)', 'Color', 'w');
    ylabel('\DeltaF/F', 'Color', 'w');
    title(sprintf('POST T%d  (%s)', POST_ID, CONNECTION_TYPE), ...
        'Color', 'w', 'FontSize', 11);
    set(ma2, 'Color', ax_bg, 'XColor', 'w', 'YColor', 'w');

    set(fig_movie, 'Color', bg);
    drawnow;
    pause(MOVIE_PAUSE_S);
end

fprintf('Movie complete.\n');

% =====================================================================
% Local functions
% =====================================================================

function out = smooth_nan(x, sigma_s, fs)
% SMOOTH_NAN  NaN-safe Gaussian smooth.
%   x       : input column vector (may contain NaNs)
%   sigma_s : Gaussian sigma in seconds
%   fs      : sample rate in Hz
%
% Strategy:
%   1. Linearly interpolate across NaN runs so the convolution does not
%      spread NaNs into neighbouring valid samples.
%   2. Gaussian-smooth the interpolated signal.
%   3. Restore NaNs at their original positions.

    x = x(:);
    nan_mask = isnan(x);

    % Interpolate over NaNs if any exist
    if any(nan_mask)
        idx      = (1:numel(x))';
        x_interp = x;
        x_interp(nan_mask) = interp1(idx(~nan_mask), x(~nan_mask), ...
                                     idx(nan_mask), 'linear', 'extrap');
    else
        x_interp = x;
    end

    % Build Gaussian kernel (truncated at +/- 3 sigma)
    sigma_samp = sigma_s * fs;
    half_w     = ceil(3 * sigma_samp);
    k_idx      = (-half_w:half_w)';
    kernel     = exp(-0.5 * (k_idx / sigma_samp).^2);
    kernel     = kernel / sum(kernel);

    % Convolve, symmetric padding to reduce edge effects
    out = conv(x_interp, kernel, 'same');

    % Restore NaNs
    out(nan_mask) = NaN;
    out = out(:);
end


