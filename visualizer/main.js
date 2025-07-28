import { PMTiles, leafletRasterLayer } from 'https://cdn.jsdelivr.net/npm/pmtiles@4.3.0/+esm';

const dataURL = 'https://pub-0405e55247634298a3056ded59cb9feb.r2.dev/'
const forwardCacheHours = 3;
const layerOpacity = 0.8;

var osm = L.tileLayer('http://{s}.tile.osm.org/{z}/{x}/{y}.png', {attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'/*, minZoom: 0, maxZoom: 15*/});
var cartodb = L.tileLayer('http://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png', {attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="http://cartodb.com/attributions">CartoDB</a>'/*, minZoom: 0, maxZoom: 5*/});
var toner = L.tileLayer('http://{s}.tile.stamen.com/toner/{z}/{x}/{y}.png', {attribution: 'Map tiles by <a href="http://stamen.com">Stamen Design</a>, under <a href="http://creativecommons.org/licenses/by/3.0">CC BY 3.0</a>. Data by <a href="http://openstreetmap.org">OpenStreetMap</a>, under <a href="http://www.openstreetmap.org/copyright">ODbL</a>.', minZoom: 0, maxZoom: 5});
var white = L.tileLayer("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAQAAAAEAAQMAAABmvDolAAAAA1BMVEX///+nxBvIAAAAH0lEQVQYGe3BAQ0AAADCIPunfg43YAAAAAAAAAAA5wIhAAAB9aK9BAAAAABJRU5ErkJggg==", {minZoom: 0, maxZoom: 5});

function addHoursToISO(isoStr, hours) {
  const date = new Date(isoStr);
  date.setHours(date.getHours() + hours);
  return date.toISOString();
}

function getTimeInterval(metadata) {
    console.log(metadata)

    const [datePart, durationPart] = metadata.latest.split('_');
    const duration = parseInt(durationPart.match(/\d+/)[0], 10);

    const startTime = datePart.replace(/T(\d{2})Z$/, 'T$1:00:00Z');
    const endTime = addHoursToISO(startTime, duration);
    return startTime + '/' + endTime;
}

let cachedLayers = {}
let currentPMTilesLayer = null;
let currentTDPMTilesLayer = null;

function showVariable(map, metadata, variable, iPressureLevel) {
    // Clear cached layers
    for (const key of Object.keys(cachedLayers)) {
        map.removeLayer(cachedLayers[key]);
        delete cachedLayers[key];
    }

    currentPMTilesLayer = null; // Already removed from the cached layers cleanse

    if(currentTDPMTilesLayer) {
        map.removeLayer(currentTDPMTilesLayer);
        currentTDPMTilesLayer = null;
    }

    const pmtilesLayer = L.tileLayer('', {}); // dummy layer
    const TDPmtiles = L.TimeDimension.Layer.extend({
    _onNewTimeLoading: function(ev) {
        const timeIndex = this._timeDimension.getAvailableTimes().indexOf(
            this._timeDimension.getCurrentTime()
        );

        for (const key of Object.keys(cachedLayers)) {
            if(key < timeIndex - forwardCacheHours || key > timeIndex + forwardCacheHours){
                this._map.removeLayer(cachedLayers[key]);
                delete cachedLayers[key];
            }
        }

        for(let i = timeIndex; i < Math.min(timeIndex + forwardCacheHours, this._timeDimension.getAvailableTimes().length); ++i) {
            if(cachedLayers[i]){
                continue;
            }

            let pmtilesUrl = `${dataURL}tiles/${metadata.latest}/${variable}/`;
            if(metadata.variables[variable].is_level) {
                pmtilesUrl += `lvl${iPressureLevel}/`
            } 
            pmtilesUrl += `h${i}.pmtiles`

            const source = new PMTiles(pmtilesUrl);
            const layer = leafletRasterLayer(source, {maxNativeZoom: 2});
            layer.setOpacity(0);
            layer.addTo(this._map);
            cachedLayers[i] = layer;
        }

        if (currentPMTilesLayer) {
            currentPMTilesLayer.setOpacity(0);
        }

        currentPMTilesLayer = cachedLayers[timeIndex];
        currentPMTilesLayer.setOpacity(layerOpacity);
    }
    });
    const tdPmtilesLayer = new TDPmtiles(pmtilesLayer, {attribution: '<a href="https://montefiore-sail.github.io/appa/">APPA</a> weather model'});
    tdPmtilesLayer.addTo(map);
    tdPmtilesLayer._onNewTimeLoading();
    currentTDPMTilesLayer = tdPmtilesLayer;
}

// Main map loading
async function setupMap() {
    const response = await fetch(dataURL + 'metadata.json')
    const metadata = await response.json()

    var map = L.map('map', {
        zoom: 5,
        center: [50.586180926650044, 5.559588296374543],
        timeDimension: true,
        timeDimensionOptions: {
            timeInterval: getTimeInterval(metadata),
            period: "PT1H"
        },
        timeDimensionControl: true,
    });

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
                console.log('Selected:', value);
                showVariable(map, metadata, value, 0)
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

    L.control.slideMenu('<p>test</p>').addTo(map);
}

setupMap();