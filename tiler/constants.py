# These are drop-in values used by the main script chaining all operations
# together.

CMAP_MAPPINGS = {
    # 'temperature': 'plasma',
    # '2m_temperature': 'plasma',
    # 'sea_surface_temperature': 'plasma',
    # '10m_u_component_of_wind': 'bwr',
    # '10m_v_component_of_wind': 'bwr',
    # 'u_component_of_wind': 'bwr',
    # 'v_component_of_wind': 'bwr',
    # 'total_precipitation': 'YlGnBu',
    # 'specific_humidity': 'YlGnBu'
}

CMAP_DEFAULT = 'jet'

# Modifying ZOOM_MIN is **NOT** supported by the web app
ZOOM_MIN = 0

# A value of 2 gives ~2GB of tile data. A value of 3, ~8GB.
ZOOM_MAX = 3