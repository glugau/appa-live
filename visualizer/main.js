import { PMTiles, leafletRasterLayer } from 'https://cdn.jsdelivr.net/npm/pmtiles@4.3.0/+esm';
import * as cu from './computeUtils.js';

const dataURL = 'https://data.appa-forecasts.download/'
const lookAheadLayers = 4;
const layerOpacity = 0.8;
const maxAvailableZoom = 2;

var osm = L.tileLayer('http://{s}.tile.osm.org/{z}/{x}/{y}.png', {attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'/*, minZoom: 0, maxZoom: 15*/});
var cartodb = L.tileLayer('http://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png', {attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="http://cartodb.com/attributions">CartoDB</a>'/*, minZoom: 0, maxZoom: 5*/});
var toner = L.tileLayer('http://{s}.tile.stamen.com/toner/{z}/{x}/{y}.png', {attribution: 'Map tiles by <a href="http://stamen.com">Stamen Design</a>, under <a href="http://creativecommons.org/licenses/by/3.0">CC BY 3.0</a>. Data by <a href="http://openstreetmap.org">OpenStreetMap</a>, under <a href="http://www.openstreetmap.org/copyright">ODbL</a>.', minZoom: 0, maxZoom: 5});
var white = L.tileLayer("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAQAAAAEAAQMAAABmvDolAAAAA1BMVEX///+nxBvIAAAAH0lEQVQYGe3BAQ0AAADCIPunfg43YAAAAAAAAAAA5wIhAAAB9aK9BAAAAABJRU5ErkJggg==", {minZoom: 0, maxZoom: 5});

let cachedPMTiles = {};
let futureLayers = [];
let currentPMTilesLayer = null;
let currentPMTilesSource = null;
let currentTDPMTilesLayer = null;
let currentPressureSelector = null;
let currentVariable = null;
let curriLvl = null;
let curriTime = -1;

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

    if(currentPMTilesLayer) {
        map.removeLayer(currentPMTilesLayer);
        currentPMTilesLayer = null;
        currentPMTilesSource = null;
    }

    const [_, durationPart] = metadata.latest.split('_');
    const duration = parseInt(durationPart.match(/\d+/)[0], 10);

    if(currentTDPMTilesLayer) {
        map.removeLayer(currentTDPMTilesLayer);
        currentTDPMTilesLayer = null;
    }

    // Take duration + 1 because of the extra hour at step 0, which is the
    // assimilation timestamp.    
    for(let iTime = 0; iTime < duration + 1; ++iTime) {
        let pmtilesUrl = `${dataURL}tiles/${metadata.latest}/${variable}/`;
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

        if (currentPMTilesLayer) {
            map.removeLayer(currentPMTilesLayer);
        }

        currentPMTilesSource = cachedPMTiles[timeIndex];

        if(timeIndex in futureLayers) {
            currentPMTilesLayer = futureLayers[timeIndex];
        } else {
            currentPMTilesLayer = leafletRasterLayer(cachedPMTiles[timeIndex], {maxNativeZoom: maxAvailableZoom});
            currentPMTilesLayer.addTo(map);
        }

        delete futureLayers[timeIndex];
        currentPMTilesLayer.setOpacity(layerOpacity);

        // Construct the future layers, and cleanup lingering ones which shouldn't
        // be there (for instance due to manually changing the time)
        for(let i = 0; i < this._timeDimension.getAvailableTimes().length; ++i) {
            if(i > timeIndex && i <= timeIndex + lookAheadLayers) {
                if(i in futureLayers) continue;

                // (commented) Only prepare layers if in play mode. Only way I found was
                // to look at the UI...
                // const el = document.querySelector('[title="Play"]');
                // if (!el || el.classList.contains('pause')) {
                futureLayers[i] = leafletRasterLayer(cachedPMTiles[i], {maxNativeZoom: maxAvailableZoom});
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
    }
    });
    const tdPmtilesLayer = new TDPmtiles(pmtilesLayer, {attribution: '<a href="https://montefiore-sail.github.io/appa/">APPA</a> weather model'});
    tdPmtilesLayer.addTo(map);
    tdPmtilesLayer._onNewTimeLoading();
    currentTDPMTilesLayer = tdPmtilesLayer;
}

function togglePressureSelector(map, metadata, show) {
    if(currentPressureSelector && show) {
        return;
    }

    if(!currentPressureSelector && !show){
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
                    showVariable(map, metadata, currentVariable, curriLvl)
                };

                select.onchange = e => runLogic(e.target.value);

                // Run logic on initial load
                setTimeout(() => runLogic(select.value), 0);

                return div;
            },

            onRemove: function(map) {}
        });
        currentPressureSelector = new PressureSelector({ position: 'topright' })
        map.addControl(currentPressureSelector);
    } else {
        map.removeControl(currentPressureSelector);
        currentPressureSelector = null;
    }
}

// Main map loading
async function setupMap() {
    const response = await fetch(dataURL + 'metadata.json')
    const metadata = await response.json()
    currentVariable = Object.keys(metadata.variables)[0];
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
        lon = ((lon + 180) % 360 + 360) % 360 - 180;
        console.log(`Clicked ${lat} ${lon}`);

        const montefioreLat = 50.58607874775542;
        const montefioreLon = 5.560189111476355;
        let montefiore = Math.abs(lat - montefioreLat) < 0.1 && Math.abs(lon - montefioreLon) < 0.1;

        let info;
        if(montefiore)
            info ='Montefiore Institute';
        else
            info = `(${lat.toFixed(5)}, ${lon.toFixed(5)})`;
        
        const { x, y, z } = cu.lngLatToTileXY(lon, lat, Math.min(map.getZoom(), maxAvailableZoom));
        const { x: px, y: py } = cu.lngLatToPixelInTile(lon, lat, z);

        const tileData = await currentPMTilesSource.getZxy(z, x, y);
        const blob = new Blob([tileData.data], {type: 'image/png'});
        const url = URL.createObjectURL(blob);


        const img = new Image();
        img.crossOrigin = 'anonymous';

        let colormap;
        if('values' in metadata['colormaps'][currentVariable]) {
            colormap = metadata['colormaps'][currentVariable];
        } else { // Is a level-based variable
            colormap = metadata['colormaps'][currentVariable][metadata.levels[curriLvl]];
        }

        img.onload = () => {
            const canvas = document.createElement('canvas');
            canvas.width = img.width;
            canvas.height = img.height;

            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0);

            const pixelX = Math.floor(px);
            const pixelY = Math.floor(py);

            const [r, g, b, a] = ctx.getImageData(pixelX, pixelY, 1, 1).data; // [r,g,b,a]
            console.log('Pixel RGBA:', r, g, b, a);
            URL.revokeObjectURL(url);

            let closestIndex = cu.closestRgb({r, g, b}, colormap['colors']);
            let closestValue = colormap['values'][closestIndex];

            info += `<br>Value: ${closestValue}`;

            L.popup()
                .setLatLng([e.latlng.lat, e.latlng.lng])
                .setContent(info)
                .openOn(map);
        };

        img.onerror = e => {
            console.error('Image load failed', e);
        };

        img.src = url;
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
                currentVariable = value;
                togglePressureSelector(map, metadata, metadata.variables[value].is_level);
                showVariable(map, metadata, currentVariable, curriLvl);
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
