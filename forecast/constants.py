PRESSURE_LEVELS = [50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000]

SURFACE_VARIABLES = [
    "2m_temperature",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "mean_sea_level_pressure",
    "sea_surface_temperature",
    "total_precipitation",
]

ATMOSPHERIC_VARIABLES = [
    "temperature",
    "u_component_of_wind",
    "v_component_of_wind",
    "geopotential",
    "specific_humidity",
]

CONTEXT_VARIABLES = [
    "toa_incident_solar_radiation",
]

VARIABLES = SURFACE_VARIABLES + ATMOSPHERIC_VARIABLES