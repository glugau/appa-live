import xarray as xr

# Your existing data loading
ds = xr.open_zarr('/home/jovyan/shared/ggluckmann/appa-forecasts/2025-07-24T06Z_PT48H.zarr')  
lats = ds['latitude'].to_numpy()  # [90, 89.75, ..., -89.75, -90]
lons = ds['longitude'].to_numpy()  # [0, 0.25, ..., 359.5, 359.75]
data_values = ds['2m_temperature'][0].to_numpy()