plate_path = 'S:\DFP\2023_DFP\2023-07-27_JaneJacques_FireflyFour_DFP-034\Plates\PlateNumber_1';
fovs = 1:180;

for fov = fovs
    fov_fig_name = fullfile(plate_path, sprintf('FOV_%04d', fov), ...
                            'YellowLaserShutter_RCaMP_Synaptic_Traces_Matrix_dF_F.fig');
    if ~isfile(fov_fig_name)
        fprintf('Skipping missing FOV: %s\n', fov_fig_name);
        continue
    end
    openfig(fov_fig_name);
    title(sprintf('FOV_%04d', fov));
end
%% 

% save rcamp images
plate_path = 'R:\QNP\2026_QNP\2026-05-08_JenniferGrooms_FireflyOne\PlateNumber_3';
fovs = 1:48;
for fov = fovs
    fov_fig_name = fullfile(plate_path, sprintf('FOV_%04d', fov), ...
                            'YellowLaserShutter_RCaMP_Synaptic_Traces_Matrix_dF_F.fig');
    if ~isfile(fov_fig_name)
        fprintf('Skipping missing FOV: %s\n', fov_fig_name);
        continue
    end
    openfig(fov_fig_name);
    title(sprintf('FOV_%04d', fov));
end