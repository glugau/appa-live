import { generateTile } from "./data.js"

var map = L.map('map', {
            center: [-9.669776090959203e-11, -0.12499999999998579],
            zoom: 5,
            minZoom: 0,
            maxZoom: 8,
        });

var CanvasLayer = L.GridLayer.extend({
    createTile: async function(coords, done){
        var error;

        // create a <canvas> element for drawing
        var tile = L.DomUtil.create('canvas', 'leaflet-tile');

        // setup tile width and height according to the options
        var size = this.getTileSize();
        tile.width = size.x;
        tile.height = size.y;

        await generateTile(coords, size, tile);



        // draw something asynchronously and pass the tile to the done() callback
        setTimeout(function() {
            done(error, tile);
        }, 1000);

        return tile;
    }
});
        
var osm = L.tileLayer('http://{s}.tile.osm.org/{z}/{x}/{y}.png', {attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors', minZoom: 0, maxZoom: 5});
var cartodb = L.tileLayer('http://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png', {attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="http://cartodb.com/attributions">CartoDB</a>', minZoom: 0, maxZoom: 5});
var toner = L.tileLayer('http://{s}.tile.stamen.com/toner/{z}/{x}/{y}.png', {attribution: 'Map tiles by <a href="http://stamen.com">Stamen Design</a>, under <a href="http://creativecommons.org/licenses/by/3.0">CC BY 3.0</a>. Data by <a href="http://openstreetmap.org">OpenStreetMap</a>, under <a href="http://www.openstreetmap.org/copyright">ODbL</a>.', minZoom: 0, maxZoom: 5});
var white = L.tileLayer("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAQAAAAEAAQMAAABmvDolAAAAA1BMVEX///+nxBvIAAAAH0lEQVQYGe3BAQ0AAADCIPunfg43YAAAAAAAAAAA5wIhAAAB9aK9BAAAAABJRU5ErkJggg==", {minZoom: 0, maxZoom: 5});

L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles © Esri'
}).addTo(map);

L.tileLayer('./tiles/{z}/{x}/{y}.png', {tms: 1, opacity: 0.9, attribution: "APPA", minZoom: 0, maxNativeZoom: 3}).addTo(map);