% SCS_MovieSplit_v17.m
% =====================================================================
% Pipeline v17 splitter (multi-protocol-step aware).
%
% For each FOV under PLATE_DIR, this script:
%   1. Picks the savefast with the highest -<N>g suffix (skipping any
%      *_RuntimeAnalysis_.savefast pre-movies). Picking by file size, like
%      the v4 splitter did, was unsafe — a smaller-numbered savefast can
%      sometimes be larger on disk and silently steal the slot.
%   2. Walks data.analysis.metadata.protocol{1..N} and classifies each step:
%        * 'Spontaneous' (or any step with empty/NaN StimulusOnFrames AND a
%          name matching SPONT_NAMES below) → SPONT step.
%        * Any step with non-empty StimulusOnFrames → STIM step.
%        * Anything else (e.g. 'LinearRamp') → skipped, log line emitted.
%   3. Slices the trace at each step's StartFrame:StopFrame, halves each
%      slice, and writes the corresponding CSVs.
%   4. Reads stim metadata directly from the savefast.
%
% Per-FOV outputs (under PLATE_DIR\v17_traces\):
%   FOV_XXXX_<base>_spont_part1.csv     (if a spont step was found)
%   FOV_XXXX_<base>_spont_part2.csv
%   FOV_XXXX_<base>_stim_part1.csv      (if a stim step was found)
%   FOV_XXXX_<base>_stim_part2.csv
%   FOV_XXXX_<base>_stim_meta.json
%
% StimulusOnFrames in the savefast are STEP-RELATIVE 1-indexed. The JSON
% stores them remapped into part1/part2 LOCAL sample numbers (also 1-indexed)
% so the Python pipeline can use them directly against the CSVs it loads.
%
% Robyn St. Laurent, May 22 2026.
% =====================================================================

% ── Run Master Pipeline startup.m ────────────────────────────────────────────
% Make sure you have access to Quiver Analysis repo and have run the standard startup function
% startup(addPaths);

clearvars
% ── Constants ─────────────────────────────────────────────────────────
FS          = 500;     % Hz, FireflyOne sample rate
SPONT_NAMES = {'Spontaneous', 'Baseline', 'Spont'};   % protocolName matches treated as spont

% ── Configuration ───────────────────────────────────────────────────────
PLATE_DIR  = 'R:\QNP\2026_QNP\2026-05-13_JenniferGrooms_FireflyOne\PlateNumber_4';
OUTPUT_DIR = fullfile(PLATE_DIR, 'v17_traces');

if ~exist(OUTPUT_DIR, 'dir')
    mkdir(OUTPUT_DIR);
    fprintf('Created output folder:\n  %s\n\n', OUTPUT_DIR);
else
    fprintf('Output folder exists:\n  %s\n\n', OUTPUT_DIR);
end

% ── Find all FOV folders ─────────────────────────────────────────────────
fov_dirs = dir(fullfile(PLATE_DIR, 'FOV_*'));
fov_dirs = fov_dirs([fov_dirs.isdir]);
if isempty(fov_dirs)
    error('No FOV_* folders found under:\n  %s', PLATE_DIR);
end
fprintf('Found %d FOV folder(s).\n\n', length(fov_dirs));

% ── Process each FOV ─────────────────────────────────────────────────────
for f = 1:length(fov_dirs)
    fov_name = fov_dirs(f).name;
    fov_path = fullfile(PLATE_DIR, fov_name);
    fprintf('=== [%d/%d] %s ===\n', f, length(fov_dirs), fov_name);

    % ── 1. Pick the highest -<N>g savefast, skipping RuntimeAnalysis ─────
    sf_files = dir(fullfile(fov_path, '*g.savefast'));
    if ~isempty(sf_files)
        sf_files = sf_files(arrayfun(@(s) ~contains(s.name, 'RuntimeAnalysis'), sf_files));
    end
    if isempty(sf_files)
        fprintf('  [SKIP] No *g.savefast file found.\n\n');
        continue;
    end
    sufs = nan(size(sf_files));
    for k = 1:numel(sf_files)
        tok = regexp(sf_files(k).name, '-(\d+)g\.savefast$', 'tokens', 'once');
        if ~isempty(tok); sufs(k) = str2double(tok{1}); end
    end
    if all(isnan(sufs))
        fprintf('  [SKIP] No savefast matched -<N>g.savefast pattern.\n\n');
        continue;
    end
    [~, max_idx] = max(sufs);
    if length(sf_files) > 1
        fprintf('  Found %d savefasts; using -%dg (%s)\n', ...
                length(sf_files), sufs(max_idx), sf_files(max_idx).name);
    end
    sf_file = sf_files(max_idx);
    sf_path = fullfile(fov_path, sf_file.name);
    [~, base_name, ~] = fileparts(sf_path);
    out_stem = sprintf('%s_%s', fov_name, base_name);
    % Skip if output already exists
    if isfile(fullfile(OUTPUT_DIR, [out_stem '_stim_meta.json']))
        fprintf('  [SKIP] Already analyzed — %s\n\n', fov_name);
        continue;
    end
    % Output paths
    csv_sp1  = fullfile(OUTPUT_DIR, [out_stem '_spont_part1.csv']);
    csv_sp2  = fullfile(OUTPUT_DIR, [out_stem '_spont_part2.csv']);
    csv_st1  = fullfile(OUTPUT_DIR, [out_stem '_stim_part1.csv']);
    csv_st2  = fullfile(OUTPUT_DIR, [out_stem '_stim_part2.csv']);
    meta_js  = fullfile(OUTPUT_DIR, [out_stem '_stim_meta.json']);

    % ── 2. Load savefast ─────────────────────────────────────────────────
    try
        fprintf('  Loading %s...\n', sf_file.name);
        data = LoadFast(sf_path);
        analysis = data.analysis;
    catch ME
        fprintf('  [ERROR] LoadFast failed: %s\n\n', ME.message);
        continue;
    end

    % ── 3. Build the trace matrix [n_samples x n_sources] ────────────────
    n_sources = length(analysis.sources);
    n_samples = length(analysis.sources(1).trace);
    fprintf('  Sources: %d   Samples: %d (%.1f s)\n', ...
            n_sources, n_samples, n_samples/FS);

    tracen = zeros(n_samples, n_sources);
    for s = 1:n_sources
        tracen(:, s) = analysis.sources(s).trace;
    end

    % ── 4. Walk protocol steps and classify ──────────────────────────────
    %     Use try/catch instead of isfield because LoadFast may return analysis
    %     as a class instance (object), in which case isfield returns false even
    %     when the property is present.  Same applies for experiment / stimSourceID
    %     access further down.
    protocol = [];
    try
        protocol = analysis.metadata.protocol;
    catch
        protocol = [];
    end
    if isempty(protocol)
        fprintf('  [SKIP] Savefast has no analysis.metadata.protocol.\n\n');
        continue;
    end
    if ~iscell(protocol); protocol = {protocol}; end   % accept struct OR cell-of-struct

    spont_step = struct('found', false);
    stim_step  = struct('found', false);
    for k = 1:numel(protocol)
        if iscell(protocol); p = protocol{k}; else; p = protocol(k); end

        nm = '';
        try; nm = char(p.protocolName); catch; nm = ''; end

        on_frames_raw = [];
        try; on_frames_raw = double(p.StimulusOnFrames); catch; on_frames_raw = []; end
        has_stim = ~isempty(on_frames_raw) && ~all(isnan(on_frames_raw(:)));

        % StartFrame / StopFrame, defensive
        sf_start = NaN; sf_stop = NaN;
        try; sf_start = double(p.StartFrame); catch; end
        try; sf_stop  = double(p.StopFrame ); catch; end

        if has_stim
            if stim_step.found
                fprintf('    step %d (%s): additional stim step ignored — first wins\n', k, nm);
                continue;
            end
            stim_step.found       = true;
            stim_step.k           = k;
            stim_step.name        = nm;
            stim_step.start_frame = sf_start;
            stim_step.stop_frame  = sf_stop;
            stim_step.on_frames   = on_frames_raw;
            stim_step.on_frames_orig = p.StimulusOnFrames;   % preserve cell or numeric original
            fprintf('    step %d: STIM   (%s) frames %d..%d\n', ...
                    k, nm, sf_start, sf_stop);
        elseif any(strcmpi(nm, SPONT_NAMES)) || isempty(on_frames_raw)
            if spont_step.found
                fprintf('    step %d (%s): additional spont step ignored — first wins\n', k, nm);
                continue;
            end
            spont_step.found       = true;
            spont_step.k           = k;
            spont_step.name        = nm;
            spont_step.start_frame = sf_start;
            spont_step.stop_frame  = sf_stop;
            fprintf('    step %d: SPONT  (%s) frames %d..%d\n', ...
                    k, nm, sf_start, sf_stop);
        else
            fprintf('    step %d: SKIP   (%s) — not classified as spont or stim\n', k, nm);
        end
    end

    if ~spont_step.found && ~stim_step.found
        fprintf('  [SKIP] No spont or stim step identified for this FOV.\n\n');
        continue;
    end

    % ── 5. Helper: split a frame range at the midpoint, write part1/part2
    %     CSVs. Returns the local split point (length of part1).
    headers = arrayfun(@(i) sprintf('T%d', i), 1:n_sources, 'UniformOutput', false);

    spont_split_local = 0;
    spont_n           = 0;
    stim_split_local  = 0;
    stim_n            = 0;

    if spont_step.found
        s_lo = spont_step.start_frame;
        s_hi = min(spont_step.stop_frame, n_samples);
        block = tracen(s_lo:s_hi, :);
        spont_n           = size(block, 1);
        spont_split_local = floor(spont_n / 2);
        if spont_split_local < 2
            fprintf('  [WARN] Spont block too short (%d samples) — skipping.\n', spont_n);
            spont_step.found = false;
        else
            sp1 = block(1:spont_split_local, :);
            sp2 = block(spont_split_local+1:end, :);
            write_csv(csv_sp1, sp1, headers);
            write_csv(csv_sp2, sp2, headers);
            fprintf('    spont split: %d / %d frames\n', size(sp1,1), size(sp2,1));
        end
    end

    if stim_step.found
        s_lo = stim_step.start_frame;
        s_hi = min(stim_step.stop_frame, n_samples);
        block = tracen(s_lo:s_hi, :);
        stim_n           = size(block, 1);
        stim_split_local = floor(stim_n / 2);
        if stim_split_local < 2
            fprintf('  [WARN] Stim block too short (%d samples) — skipping.\n', stim_n);
            stim_step.found = false;
        else
            st1 = block(1:stim_split_local, :);
            st2 = block(stim_split_local+1:end, :);
            write_csv(csv_st1, st1, headers);
            write_csv(csv_st2, st2, headers);
            fprintf('    stim split: %d / %d frames\n', size(st1,1), size(st2,1));
        end
    end

    % ── 6. Stim metadata: stimSourceID, StimulusOnFrames remap ───────────
    in_stim_mask = false(n_sources, 1);
    ids_cell = {};

    try
        ids_cell = analysis.metadata.experiment.stimSourceID;
    catch
        % stimSourceID not present — build from dmdMasks + PixelIdxList
        try
            dmd_masks      = analysis.metadata.experiment.dmdMasks;
            n_masks        = numel(dmd_masks);
            ids_cell       = cell(n_masks, 1);
            movie_size     = analysis.sources(1).movieSize;
            H              = movie_size(2);
            W              = movie_size(3);
            total_px       = H * W;
            overlap_thresh = 0.9;

            for k = 1:n_masks
                mask_px  = double(dmd_masks{k}(:));
                mask_px  = mask_px(mask_px >= 1 & mask_px <= total_px);
                mask_set = false(total_px, 1);
                mask_set(mask_px) = true;

                src_ids = [];
                for s = 1:n_sources
                    src_px    = double(analysis.sources(s).PixelIdxList(:));
                    src_px    = src_px(src_px >= 1 & src_px <= total_px);
                    n_overlap = sum(mask_set(src_px));
                    frac      = n_overlap / numel(src_px);
                    if frac >= overlap_thresh
                        src_ids(end+1) = s; %#ok<AGROW>
                    end
                end
                ids_cell{k} = src_ids(:);
            end
            fprintf('  Built ids_cell from dmdMasks: %d masks, thresh=%.2f\n', ...
                    n_masks, overlap_thresh);
        catch e
            fprintf('  dmdMasks lookup failed: %s\n', e.message);
            ids_cell = {};
        end
    end

    % Populate in_stim_mask from ids_cell
    if iscell(ids_cell)
        for k = 1:numel(ids_cell)
            inner = ids_cell{k};
            while iscell(inner) && numel(inner) == 1
                inner = inner{1};
            end
            if ~isempty(inner)
                ids = double(inner(:));
                ids = ids(ids >= 1 & ids <= n_sources);
                in_stim_mask(ids) = true;
            end
        end
    elseif isnumeric(ids_cell) && ~isempty(ids_cell)
        ids = double(ids_cell(:));
        ids = ids(ids >= 1 & ids <= n_sources);
        in_stim_mask(ids) = true;
    end

    % StimulusOnFrames are step-relative 1-indexed.
    % Remap to part1/part2 local sample numbers (also 1-indexed).
    sf_part1 = [];
    sf_part2 = [];
    if stim_step.found && stim_split_local > 0
        on = stim_step.on_frames(:);
        on = on(~isnan(on));
        on = on(on >= 1 & on <= stim_n);
        sf_part1 = on(on <= stim_split_local);
        sf_part2 = on(on >  stim_split_local) - stim_split_local;
    end

    % ── Per-source stim frames ─────────────────────────────────────────────
    stim_frames_per_source = struct();
    if stim_step.found && stim_split_local > 0 ...
            && iscell(ids_cell) && numel(ids_cell) > 0 ...
            && ~isempty(stim_step.on_frames)
        raw_on  = double(stim_step.on_frames);   % rows = masks, cols = stim/comb
        n_masks = numel(ids_cell);
        n_rows  = size(raw_on, 1);

        % Pre-initialise empty entries for every source
        for s = 1:n_sources
            stim_frames_per_source.(sprintf('T%d', s)) = ...
                struct('part1', [], 'part2', []);
        end

        for k = 1:min(n_masks, n_rows)
            mf = raw_on(k, :);
            mf = mf(~isnan(mf) & mf >= 1 & mf <= stim_n);
            if isempty(mf), continue; end
            mf_p1 = mf(mf <= stim_split_local);
            mf_p2 = mf(mf >  stim_split_local) - stim_split_local;

            inner = ids_cell{k};
            while iscell(inner) && numel(inner) == 1
                inner = inner{1};
            end
            if isempty(inner), continue; end
            src_ids = double(inner(:));
            src_ids = src_ids(src_ids >= 1 & src_ids <= n_sources);

            for ii = 1:numel(src_ids)
                sid    = src_ids(ii);
                field  = sprintf('T%d', sid);
                cur_p1 = stim_frames_per_source.(field).part1;
                cur_p2 = stim_frames_per_source.(field).part2;
                stim_frames_per_source.(field) = struct( ...
                    'part1', [cur_p1(:); mf_p1(:)]', ...
                    'part2', [cur_p2(:); mf_p2(:)]');
            end
        end
    end

    % ── 7. Assemble metadata struct and write JSON ───────────────────────
    meta = struct();
    meta.fov                 = fov_name;
    meta.savefast            = sf_file.name;
    meta.fs                  = FS;
    meta.n_sources           = n_sources;

    meta.spont_present       = spont_step.found;
    if spont_step.found
        meta.spont_step_name   = spont_step.name;
        meta.spont_start_frame = spont_step.start_frame;   % absolute frame in original trace
        meta.spont_stop_frame  = spont_step.stop_frame;
        meta.spont_n_samples   = spont_n;
        meta.spont_split_local = spont_split_local;
    end

    meta.stim_present        = stim_step.found;
    if stim_step.found
        meta.stim_step_name    = stim_step.name;
        meta.stim_start_frame  = stim_step.start_frame;
        meta.stim_stop_frame   = stim_step.stop_frame;
        meta.stim_n_samples    = stim_n;
        meta.stim_n_samples    = stim_n;
        meta.stim_split_local  = stim_split_local;
        meta.stim_frames_part1 = sf_part1(:)';
        meta.stim_frames_part2 = sf_part2(:)';
    end

    meta.stim_frames_per_source = stim_frames_per_source;
    meta.stim_mask_sources      = find(in_stim_mask)';

    % Per-source spatial centroids (row, col) from analysis.sources(s).blobInfo.
    % Used by Python's plot_spaghetti_overlay to draw the connectivity map.
    centroid_row = nan(1, n_sources);
    centroid_col = nan(1, n_sources);
    for s = 1:n_sources
        try
            r = double(analysis.sources(s).blobInfo.row);
            c = double(analysis.sources(s).blobInfo.col);
            if ~isnan(r) && ~isnan(c)
                centroid_row(s) = r;
                centroid_col(s) = c;
            end
        catch
            % source has no blobInfo — leave as NaN
        end
    end
    meta.source_centroid_row = centroid_row;
    meta.source_centroid_col = centroid_col;

    write_json(meta_js, meta);

    % Print exactly what was written, and what (if anything) was skipped.
    written = {};
    if spont_step.found
        written{end+1} = 'spont_part{1,2}.csv';
    end
    if stim_step.found
        written{end+1} = 'stim_part{1,2}.csv';
    end
    written{end+1} = 'stim_meta.json';
    parts = strjoin(written, ' + ');
    if spont_step.found && stim_step.found
        skipped = '';
    elseif spont_step.found
        skipped = '  (no stim step in this savefast)';
    elseif stim_step.found
        skipped = '  (no spont step in this savefast)';
    else
        skipped = '  (neither spont nor stim step found)';
    end
    fprintf('  Wrote: %s_%s%s\n\n', out_stem, parts, skipped);
    
    clear tracen sp1 sp2 st1 st2 block analysis data;
end

fprintf('===== Batch split complete =====\n');
fprintf('All output files saved to:\n  %s\n', OUTPUT_DIR);

% =====================================================================
% Contrast enhance supplemental figs
Save_SuppFigs
% =====================================================================

% =====================================================================
% Local functions (must appear at end of script)
% =====================================================================

function write_csv(filepath, data, headers)
    fid = fopen(filepath, 'w');
    if fid == -1
        error('Cannot open for writing: %s', filepath);
    end
    fprintf(fid, '%s\n', strjoin(headers, ','));
    if ~isempty(data)
        fmt = [repmat('%.8g,', 1, size(data,2)-1), '%.8g\n'];
        fprintf(fid, fmt, data');
    end
    fclose(fid);
    fprintf('    Saved: %s\n', filepath);
end

function write_json(filepath, s)
    txt = jsonencode(s, 'PrettyPrint', true);
    fid = fopen(filepath, 'w');
    if fid == -1
        error('Cannot open for writing: %s', filepath);
    end
    fwrite(fid, txt, 'char');
    fclose(fid);
    fprintf('    Saved: %s\n', filepath);
end
