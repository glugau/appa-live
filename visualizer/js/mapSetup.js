import { baseLayers } from './baseLayers.js';
import { CONFIG } from './config.js';
import { state } from './state.js';
import { createVariableSelector } from './controls.js';
import { makePopup } from './popup.js';
import * as cu from './computeUtils.js';

export async function setupMap() {
    const response = await fetch(CONFIG.DATA_URL + 'metadata.json');
    const metadata = await response.json();
    state.currVariable = Object.keys(metadata.variables)[0];
    state.curriLvl = 0;

    const map = L.map('map', {
        zoom: 5,
        center: [50.586180926650044, 5.559588296374543],
        timeDimension: true,
        timeDimensionOptions: {
            timeInterval: cu.getTimeInterval(metadata),
            period: "PT1H"
        },
        fadeAnimation: false
    });

    // Add event listeners
    map.on('click', async function(e) {
        makePopup(e.latlng.lat, e.latlng.lng, map, metadata);
    });

    map.on('popupclose', () => {
        state.popupLatLng = null;
    });

    // Add controls
    L.control.timeDimension({
        timeDimension: map.timeDimension,
        maxSpeed: 2,
    }).addTo(map);

    baseLayers.osm.addTo(map);
    
    const variableSelector = createVariableSelector(map, metadata);
    map.addControl(variableSelector);

    return { map, metadata };
}