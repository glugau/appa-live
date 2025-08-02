export const CONFIG = {
    // Data URL containing the 'tiles' folder
    DATA_URL: 'https://data.appa-forecasts.download/',

    // When at time t, invisible layers will be loaded up to t +
    // LOOK_AHEAD_LAYERS so that playback is smooth. Increasing this can cause
    // performance issues (zooming or panning requires loading all of those
    // layers for the new viewport), and decreasing it may worsen the live
    // playback experience.
    LOOK_AHEAD_LAYERS: 4, 

    // Opacity of the weather data layer that is displayed above the continental
    // map data
    LAYER_OPACITY: 0.8,
};