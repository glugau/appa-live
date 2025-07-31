import { PMTiles, leafletRasterLayer } from 'https://cdn.jsdelivr.net/npm/pmtiles@4.3.0/+esm';
import * as cu from './computeUtils.js';
import UNITS from './units.js';

const DATA_URL = 'https://data.appa-forecasts.download/'
const LOOK_AHEAD_LAYERS = 4;
const LAYER_OPACITY = 0.8;
const MAX_AVAILABLE_ZOOM = 2;

var osm = L.tileLayer('http://{s}.tile.osm.org/{z}/{x}/{y}.png', {attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'/*, minZoom: 0, maxZoom: 15*/});
var cartodb = L.tileLayer('http://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png', {attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="http://cartodb.com/attributions">CartoDB</a>'/*, minZoom: 0, maxZoom: 5*/});
var toner = L.tileLayer('http://{s}.tile.stamen.com/toner/{z}/{x}/{y}.png', {attribution: 'Map tiles by <a href="http://stamen.com">Stamen Design</a>, under <a href="http://creativecommons.org/licenses/by/3.0">CC BY 3.0</a>. Data by <a href="http://openstreetmap.org">OpenStreetMap</a>, under <a href="http://www.openstreetmap.org/copyright">ODbL</a>.', minZoom: 0, maxZoom: 5});
var white = L.tileLayer("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAQAAAAEAAQMAAABmvDolAAAAA1BMVEX///+nxBvIAAAAH0lEQVQYGe3BAQ0AAADCIPunfg43YAAAAAAAAAAA5wIhAAAB9aK9BAAAAABJRU5ErkJggg==", {minZoom: 0, maxZoom: 5});

let cachedPMTiles = {};
let futureLayers = [];
let currPMTilesLayer = null;
let currPMTilesSource = null;
let currTDPMTilesLayer = null;
let currPressureSelector = null;
let currVariable = null;
let curriLvl = null;
let curriTime = -1;
let popupLatLng = null;
let currLegend = null;

function showVariable(map, metadata, variable, iPressureLevel) {
    curriTime = -1;
    // Clear cached layers
    for (const key of Object.keys(cachedPMTiles)) {
        delete cachedPMTiles[key];
    }

    for (const key of Object.keys(futureLayers)) {
        map.removeLayer(futureLayers[key]);
        delete futureLayers[key];
    }

    if(currPMTilesLayer) {
        map.removeLayer(currPMTilesLayer);
        currPMTilesLayer = null;
        currPMTilesSource = null;
    }

    const [_, durationPart] = metadata.latest.split('_');
    const duration = parseInt(durationPart.match(/\d+/)[0], 10);

    if(currTDPMTilesLayer) {
        map.removeLayer(currTDPMTilesLayer);
        currTDPMTilesLayer = null;
    }

    // Take duration + 1 because of the extra hour at step 0, which is the
    // assimilation timestamp.    
    for(let iTime = 0; iTime < duration + 1; ++iTime) {
        let pmtilesUrl = `${DATA_URL}tiles/${metadata.latest}/${variable}/`;
        if(metadata.variables[variable].is_level) {
            pmtilesUrl += `lvl${iPressureLevel}/`
        } 
        pmtilesUrl += `h${iTime}.pmtiles`
        const source = new PMTiles(pmtilesUrl);
        cachedPMTiles[iTime] = source;
    }


    const pmtilesLayer = L.tileLayer('', {}); // dummy layer
    const TDPmtiles = L.TimeDimension.Layer.extend({
    _onNewTimeLoading: function(ev) {
        const timeIndex = this._timeDimension.getAvailableTimes().indexOf(
            this._timeDimension.getCurrentTime()
        );

        // Play/Pause button rapidfires events for some reason
        if(timeIndex == curriTime) return;
        curriTime = timeIndex;

        if (currPMTilesLayer) {
            map.removeLayer(currPMTilesLayer);
        }

        currPMTilesSource = cachedPMTiles[timeIndex];

        if(timeIndex in futureLayers) {
            currPMTilesLayer = futureLayers[timeIndex];
        } else {
            currPMTilesLayer = leafletRasterLayer(cachedPMTiles[timeIndex], {maxNativeZoom: MAX_AVAILABLE_ZOOM});
            currPMTilesLayer.addTo(map);
        }

        delete futureLayers[timeIndex];
        currPMTilesLayer.setOpacity(LAYER_OPACITY);

        // Construct the future layers, and cleanup lingering ones which shouldn't
        // be there (for instance due to manually changing the time)
        for(let i = 0; i < this._timeDimension.getAvailableTimes().length; ++i) {
            if(i > timeIndex && i <= timeIndex + LOOK_AHEAD_LAYERS) {
                if(i in futureLayers) continue;

                // (commented) Only prepare layers if in play mode. Only way I found was
                // to look at the UI...
                // const el = document.querySelector('[title="Play"]');
                // if (!el || el.classList.contains('pause')) {
                futureLayers[i] = leafletRasterLayer(cachedPMTiles[i], {maxNativeZoom: MAX_AVAILABLE_ZOOM});
                futureLayers[i].addTo(map);
                futureLayers[i].setOpacity(0);
                // } else {
                // }
            } else {
                if(i in futureLayers){
                    map.removeLayer(futureLayers[i]);
                    delete futureLayers[i];
                }
            }
        }

        // If a popup exists, update it
        if(popupLatLng != null) {
            makePopup(popupLatLng[0], popupLatLng[1], map, metadata);
        }
    }
    });
    const tdPmtilesLayer = new TDPmtiles(pmtilesLayer, {attribution: '<a href="https://montefiore-sail.github.io/appa/">APPA</a> weather model'});
    tdPmtilesLayer.addTo(map);
    tdPmtilesLayer._onNewTimeLoading();
    currTDPMTilesLayer = tdPmtilesLayer;

    addLegend(map, metadata, variable, iPressureLevel);
}

function togglePressureSelector(map, metadata, show) {
    if(currPressureSelector && show) {
        return;
    }

    if(!currPressureSelector && !show){
        return;
    }

    if(show) {
        const PressureSelector = L.Control.extend({
            onAdd: function(map) {
                const div = L.DomUtil.create('div', 'leaflet-bar');
                div.style.background = 'white';
                div.style.padding = '4px';
                const label = L.DomUtil.create('label', '', div);
                label.textContent = 'Pressure level (hPa)';
                label.style.marginRight = '4px';
                const select = L.DomUtil.create('select', '', div);

                // Prevent map interactions when interacting with control
                L.DomEvent.disableClickPropagation(div);
                L.DomEvent.disableScrollPropagation(div);

                metadata.levels.forEach(v => {
                    const opt = document.createElement('option');
                    opt.value = v;
                    opt.textContent = v;
                    select.appendChild(opt);
                });

                const runLogic = value => {
                    curriLvl = metadata.levels.indexOf(+value);
                    showVariable(map, metadata, currVariable, curriLvl)
                };

                select.onchange = e => runLogic(e.target.value);

                // Run logic on initial load
                setTimeout(() => runLogic(select.value), 0);

                return div;
            },

            onRemove: function(map) {}
        });
        currPressureSelector = new PressureSelector({ position: 'topright' })
        map.addControl(currPressureSelector);
    } else {
        map.removeControl(currPressureSelector);
        currPressureSelector = null;
    }
}

async function makePopup(lat, lon, map, metadata) {
    let deltaLon = Math.floor((lon + 180) / 360) * 360;
    lon = ((lon + 180) % 360 + 360) % 360 - 180;

    const montefioreLat = 50.58607874775542;
    const montefioreLon = 5.560189111476355;
    let montefiore = Math.abs(lat - montefioreLat) < 0.2 && Math.abs(lon - montefioreLon) < 0.2;

    let info;
    if(montefiore) {
        info ='Montefiore Institute';
        lon = montefioreLon;
        lat = montefioreLat;
    }
    else
        info = `(${lat.toFixed(5)}, ${lon.toFixed(5)})`;
    
    const { x, y, z } = cu.lngLatToTileXY(lon, lat, Math.min(map.getZoom(), MAX_AVAILABLE_ZOOM));
    const { x: px, y: py } = cu.lngLatToPixelInTile(lon, lat, z);

    const tileData = await currPMTilesSource.getZxy(z, x, y);
    const blob = new Blob([tileData.data], {type: 'image/png'});
    const url = URL.createObjectURL(blob);


    const img = new Image();
    img.crossOrigin = 'anonymous';

    let colormap;
    if('values' in metadata['colormaps'][currVariable]) {
        colormap = metadata['colormaps'][currVariable];
    } else { // Is a level-based variable
        colormap = metadata['colormaps'][currVariable][metadata.levels[curriLvl]];
    }

    img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = img.width;
        canvas.height = img.height;

        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0);

        const pixelX = Math.floor(px);
        const pixelY = Math.floor(py);

        const [r, g, b, a] = ctx.getImageData(pixelX, pixelY, 1, 1).data;
        URL.revokeObjectURL(url);

        let closestIndex = cu.closestRgb({r, g, b}, colormap['colors']);
        let closestValue = colormap['values'][closestIndex];

        let units = currVariable in UNITS ? UNITS[currVariable] : '(Unknown units)';
        info += `<br>${closestValue.toFixed(6)} ${units}`;

        L.popup()
            .setLatLng([lat, lon + deltaLon])
            .setContent(info)
            .openOn(map);
        popupLatLng = [lat, lon + deltaLon];
    }

    img.onerror = e => {
            console.error('Image load failed', e);
    };

    img.src = url;
}

function addLegend(map, metadata, variable, iLevel) {
    if (currLegend) {
        try { map.removeControl(currLegend); } catch (e) {}
    }
    
    currLegend = L.control({ position: 'bottomright' });
    currLegend.onAdd = function(map) {
        const div = L.DomUtil.create('div', 'info legend');
        div.style.background = 'white';
        div.style.padding = '6px';
        div.style.fontSize = '10px';
        div.style.position = 'relative';
        div.style.userSelect = 'none';
        div.style.display = 'flex';
        div.style.flexDirection = 'column';
        div.style.alignItems = 'center';
        div.style.gap = '4px';
        
        let values, colors;
        if (metadata.variables[variable].is_level) {
            values = metadata.colormaps[variable][metadata.levels[iLevel]].values;
            colors = metadata.colormaps[variable][metadata.levels[iLevel]].colors;
        } else {
            values = metadata.colormaps[variable].values;
            colors = metadata.colormaps[variable].colors;
        }
        
        const colorSteps = 100;
        const labelCount = 5;
        const stepSize = Math.floor(values.length / colorSteps);
        
        // Add units title
        let units = currVariable in UNITS ? UNITS[currVariable] : '(Unknown units)';
        const unitsLabel = document.createElement('div');
        unitsLabel.textContent = `Units: ${units}`;
        unitsLabel.style.fontSize = '10px';
        unitsLabel.style.fontWeight = 'bold';
        unitsLabel.style.textAlign = 'center';
        unitsLabel.style.marginBottom = '2px';
        unitsLabel.style.userSelect = 'none';
        
        // Container for colorbar and labels
        const legendContent = document.createElement('div');
        legendContent.style.display = 'flex';
        legendContent.style.alignItems = 'center';
        legendContent.style.gap = '8px';
        
        // Color bar container
        const colorBar = document.createElement('div');
        colorBar.style.display = 'flex';
        colorBar.style.flexDirection = 'column-reverse'; // Reverse so high values are at top
        colorBar.style.height = '150px';
        colorBar.style.width = '20px';
        colorBar.style.position = 'relative';
        
        // Create color segments
        for (let i = 0; i < colorSteps; i++) {
            const idx = i * stepSize;
            const { r, g, b } = colors[idx];
            const box = document.createElement('div');
            box.style.backgroundColor = `rgb(${r},${g},${b})`;
            box.style.flex = '1';
            box.style.width = '100%';
            colorBar.appendChild(box);
        }
        
        // Labels container
        const labelsContainer = document.createElement('div');
        labelsContainer.style.display = 'flex';
        labelsContainer.style.flexDirection = 'column';
        labelsContainer.style.justifyContent = 'space-between';
        labelsContainer.style.height = '150px';
        labelsContainer.style.fontSize = '9px';
        labelsContainer.style.userSelect = 'none';
        
        // Add labels (from high to low to match the reversed colorbar)
        for (let i = labelCount; i >= 0; i--) {
            const labelIdx = i * Math.floor(colorSteps / labelCount) * stepSize;
            const val = values[Math.min(labelIdx, values.length - 1)];
            const label = document.createElement('div');
            label.textContent = val.toFixed(2);
            label.style.whiteSpace = 'nowrap';
            label.style.lineHeight = '1';
            labelsContainer.appendChild(label);
        }
        
        legendContent.appendChild(colorBar);
        legendContent.appendChild(labelsContainer);
        
        div.appendChild(unitsLabel);
        div.appendChild(legendContent);
        
        return div;
    };
    
    currLegend.addTo(map);
}



// Main map loading
async function setupMap() {
    const response = await fetch(DATA_URL + 'metadata.json')
    const metadata = await response.json()
    currVariable = Object.keys(metadata.variables)[0];
    curriLvl = 0;

    var map = L.map('map', {
        zoom: 5,
        center: [50.586180926650044, 5.559588296374543],
        timeDimension: true,
        timeDimensionOptions: {
            timeInterval: cu.getTimeInterval(metadata),
            period: "PT1H"
        },
        // timeDimensionControl: true,
        fadeAnimation: false
    });

    
    map.on('click', async function(e) {
        let lat = e.latlng.lat;
        let lon = e.latlng.lng;
        
        makePopup(lat, lon, map, metadata);
    });

    map.on('popupclose', () => {
        popupLatLng = null;
    });


    L.control.timeDimension({
        timeDimension: map.timeDimension,
        maxSpeed: 2,
    }).addTo(map);

    osm.addTo(map);

    // Setup the variable selector (top right)
    const VariableSelector = L.Control.extend({
        onAdd: function(map) {
            const div = L.DomUtil.create('div', 'leaflet-bar');
            const select = L.DomUtil.create('select', '', div);

            // Prevent map interactions when interacting with control
            L.DomEvent.disableClickPropagation(div);
            L.DomEvent.disableScrollPropagation(div);

            Object.keys(metadata.variables).forEach(v => {
                const opt = document.createElement('option');
                opt.value = v;
                opt.textContent = v;
                select.appendChild(opt);
            });

            const runLogic = value => {
                currVariable = value;
                togglePressureSelector(map, metadata, metadata.variables[value].is_level);
                showVariable(map, metadata, currVariable, curriLvl);
            };

            select.onchange = e => runLogic(e.target.value);

            // Run logic on initial load
            setTimeout(() => runLogic(select.value), 0);

            return div;
        },

        onRemove: function(map) {}
    });
    const variableSelector = new VariableSelector({ position: 'topright' });
    map.addControl(variableSelector);
}

setupMap();
