import { PMTiles, leafletRasterLayer } from 'https://cdn.jsdelivr.net/npm/pmtiles@4.3.0/+esm';
import { state, resetState } from './state.js';
import { CONFIG } from './config.js';
import { addLegend } from './legend.js';
import { makePopup } from './popup.js';

export function showVariable(map, metadata, variable, iPressureLevel) {
    state.curriTime = -1;
    // Clear cached layers
    for (const key of Object.keys(state.cachedPMTiles)) {
        delete state.cachedPMTiles[key];
    }

    for (const key of Object.keys(state.futureLayers)) {
        map.removeLayer(state.futureLayers[key]);
        delete state.futureLayers[key];
    }

    if(state.currPMTilesLayer) {
        map.removeLayer(state.currPMTilesLayer);
        state.currPMTilesLayer = null;
        state.currPMTilesSource = null;
    }

    const [_, durationPart] = metadata.latest.split('_');
    const duration = parseInt(durationPart.match(/\d+/)[0], 10);

    if(state.currTDPMTilesLayer) {
        map.removeLayer(state.currTDPMTilesLayer);
        state.currTDPMTilesLayer = null;
    }

    // Take duration + 1 because of the extra hour at step 0, which is the
    // assimilation timestamp.    
    for(let iTime = 0; iTime < duration + 1; ++iTime) {
        let pmtilesUrl = `${CONFIG.DATA_URL}tiles/${metadata.latest}/${variable}/`;
        if(metadata.variables[variable].is_level) {
            pmtilesUrl += `lvl${iPressureLevel}/`
        } 
        pmtilesUrl += `h${iTime}.pmtiles`
        const source = new PMTiles(pmtilesUrl);
        state.cachedPMTiles[iTime] = source;
    }


    const pmtilesLayer = L.tileLayer('', {}); // dummy layer
    const TDPmtiles = L.TimeDimension.Layer.extend({
    _onNewTimeLoading: function(ev) {
        const timeIndex = this._timeDimension.getAvailableTimes().indexOf(
            this._timeDimension.getCurrentTime()
        );

        // Play/Pause button rapidfires events for some reason
        if(timeIndex == state.curriTime) return;
        state.curriTime = timeIndex;

        if (state.currPMTilesLayer) {
            map.removeLayer(state.currPMTilesLayer);
        }

        state.currPMTilesSource = state.cachedPMTiles[timeIndex];

        if(timeIndex in state.futureLayers) {
            state.currPMTilesLayer = state.futureLayers[timeIndex];
        } else {
            state.currPMTilesLayer = leafletRasterLayer(state.cachedPMTiles[timeIndex], {maxNativeZoom: metadata.zoom_max});
            state.currPMTilesLayer.addTo(map);
        }

        delete state.futureLayers[timeIndex];
        state.currPMTilesLayer.setOpacity(CONFIG.LAYER_OPACITY);

        // Construct the future layers, and cleanup lingering ones which shouldn't
        // be there (for instance due to manually changing the time)
        for(let i = 0; i < this._timeDimension.getAvailableTimes().length; ++i) {
            if(i > timeIndex && i <= timeIndex + CONFIG.LOOK_AHEAD_LAYERS) {
                if(i in state.futureLayers) continue;

                // (commented) Only prepare layers if in play mode. Only way I found was
                // to look at the UI...
                // const el = document.querySelector('[title="Play"]');
                // if (!el || el.classList.contains('pause')) {
                state.futureLayers[i] = leafletRasterLayer(state.cachedPMTiles[i], {maxNativeZoom: metadata.zoom_max});
                state.futureLayers[i].addTo(map);
                state.futureLayers[i].setOpacity(0);
                // } else {
                // }
            } else {
                if(i in state.futureLayers){
                    map.removeLayer(state.futureLayers[i]);
                    delete state.futureLayers[i];
                }
            }
        }

        // If a popup exists, update it
        if(state.popupLatLng != null) {
            makePopup(state.popupLatLng[0], state.popupLatLng[1], map, metadata);
        }
    }
    });
    const tdPmtilesLayer = new TDPmtiles(pmtilesLayer, {attribution: '<a href="https://montefiore-sail.github.io/appa/">APPA</a> weather model'});
    tdPmtilesLayer.addTo(map);
    tdPmtilesLayer._onNewTimeLoading();
    state.currTDPMTilesLayer = tdPmtilesLayer;

    addLegend(map, metadata, variable, iPressureLevel);
}