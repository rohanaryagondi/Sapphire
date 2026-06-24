% Load supplemental images from the premovie and increase contrast
function Save_SuppFigs(PLATE_DIR, fov_dirs)
baseDir = PLATE_DIR;
for i = 1:length(fov_dirs)
    fovName = sprintf('FOV_%04d', i);
    fovDir = fullfile(baseDir, fovName);
    % Skip if already done
    enhGfp   = fullfile(fovDir, sprintf('SupplementalImages_GFP_%s_enhanced.png',   fovName));
    enhRcamp = fullfile(fovDir, sprintf('SupplementalImages_RCaMP_%s_enhanced.png', fovName));
    if isfile(enhGfp) && isfile(enhRcamp)
        fprintf('%d (skip) ', i);
        continue;
    end
    
    qsmFiles = dir(fullfile(fovDir, '*-1g.qsm'));
    if isempty(qsmFiles), warning('No file in %s, skipping.', fovDir); continue; end
    
    movie = LoadMovie(fullfile(fovDir, qsmFiles(1).name));
    suppIm = GetSupplementalImages(movie);
    
    % GFP
    rawIm = suppIm('BluePower_GFP');
    gfpPath = fullfile(fovDir, sprintf('SupplementalImages_GFP_%s.png', fovName));
    imwrite(mat2gray(rawIm), gfpPath);
    EnhanceSuppImages(gfpPath, fullfile(fovDir, sprintf('SupplementalImages_GFP_%s_enhanced.png', fovName)));

    % RCaMP
    rawIm = suppIm('YellowLaserShutter_RCaMP');
    rcampPath = fullfile(fovDir, sprintf('SupplementalImages_RCaMP_%s.png', fovName));
    imwrite(mat2gray(rawIm), rcampPath);
    EnhanceSuppImages(rcampPath, fullfile(fovDir, sprintf('SupplementalImages_RCaMP_%s_enhanced.png', fovName)));

    fprintf(num2str(i));
end
fprintf('--- Done saving supp figs!\n');
end