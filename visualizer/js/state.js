// Global state
export const state = {
    cachedPMTiles: {},
    futureLayers: [],
    currPMTilesLayer: null,
    currPMTilesSource: null,
    currTDPMTilesLayer: null,
    currPressureSelector: null,
    currVariable: null,
    curriLvl: null,
    curriTime: -1,
    popupLatLng: null,
    currLegend: null
};

export function resetState() {
    // Clear cached layers
    for (const key of Object.keys(state.cachedPMTiles)) {
        delete state.cachedPMTiles[key];
    }
    
    for (const key of Object.keys(state.futureLayers)) {
        delete state.futureLayers[key];
    }
    
    state.currPMTilesLayer = null;
    state.currPMTilesSource = null;
    state.currTDPMTilesLayer = null;
    state.curriTime = -1;
}