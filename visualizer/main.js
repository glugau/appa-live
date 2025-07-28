import { PMTiles, leafletRasterLayer } from 'https://cdn.jsdelivr.net/npm/pmtiles@4.3.0/+esm';

const dataURL = 'https://pub-0405e55247634298a3056ded59cb9feb.r2.dev/'

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

let currentPMTilesLayer = null;

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


    const pmtilesLayer = L.tileLayer('', {}); // dummy layer
    const TDPmtiles = L.TimeDimension.Layer.extend({
    _onNewTimeLoading: function(ev) {
        const timeIndex = this._timeDimension.getAvailableTimes().indexOf(
            this._timeDimension.getCurrentTime()
        );

        console.log(timeIndex)

        const pmtilesUrl = `${dataURL}tiles/2025-07-28T00Z_PT48H/2m_temperature/h${timeIndex}.pmtiles`;
        const source = new PMTiles(pmtilesUrl);
        const layer = leafletRasterLayer(source, {tms: 1,});

         if (currentPMTilesLayer) {
            this._map.removeLayer(currentPMTilesLayer);
        }

        layer.addTo(this._map);
        currentPMTilesLayer = layer;
    }
    });
    const tdPmtilesLayer = new TDPmtiles(pmtilesLayer);
    tdPmtilesLayer.addTo(map);
}

setupMap();

// L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
//     attribution: 'Tiles © Esri'
// }).addTo(map);

// leafletRasterLayer(p, {opacity: 0.8, attribution: '<a href="https://montefiore-sail.github.io/appa/">APPA</a> weather model', minZoom: 0, maxNativeZoom: 2})
// .addTo(map);

// L.tileLayer('https://appa.nvidia-oci.saturnenterprise.io/tiles/specific_humidity/lvl10/h0/{z}/{x}/{y}.png', 
//     {tms: 1, opacity: 0.8, attribution: '<a href="https://montefiore-sail.github.io/appa/">APPA</a> weather model', minZoom: 0, maxNativeZoom: 2}).addTo(map);