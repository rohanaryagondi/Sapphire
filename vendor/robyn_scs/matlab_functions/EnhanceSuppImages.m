
function enhanceSuppImages(inputPath, outputPath)
    % Load the image
    img = imread(inputPath);
    %% 1. CONTRAST ENHANCEMENT
    img_contrast = imadjust(img, [0 50/255], [0 1]);

    %% 2. SHARPEN — tighten edges
    img_sharp = imsharpen(img_contrast, 'Radius', 1, 'Amount', 1.5);

    %% 3. ERODE — shrinks bright regions (makes spots smaller/tighter)
    % Increase disk radius (1→2→3) to shrink spots more aggressively
    se = strel('disk', 1);
    img_erode = imerode(img_sharp, se);

    %% 4. FINAL CONTRAST STRETCH — recover brightness lost in erosion
    img_out = imadjust(img_erode, [0 0.8], [0 1]);

    %% Display
%     figure;
%     subplot(4,1,1); imshow(img);          title('Original');
%     subplot(4,1,2); imshow(img_contrast); title('Contrast Stretched');
%     subplot(4,1,3); imshow(img_erode);    title('Eroded (smaller spots)');
%     subplot(4,1,4); imshow(img_out);      title('Final');
%     figure;
%     imshow(img_erode);
    %% Save
    imwrite(img_out, outputPath);