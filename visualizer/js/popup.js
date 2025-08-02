import { state } from './state.js';
import * as cu from './computeUtils.js';
import { CONFIG } from './config.js';

export async function makePopup(lat, lon, map, metadata) {
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
    
    const { x, y, z } = cu.lngLatToTileXY(lon, lat, Math.min(map.getZoom(), metadata.zoom_max));
    const { x: px, y: py } = cu.lngLatToPixelInTile(lon, lat, z);

    const tileData = await state.currPMTilesSource.getZxy(z, x, y);
    const blob = new Blob([tileData.data], {type: 'image/png'});
    const url = URL.createObjectURL(blob);


    const img = new Image();
    img.crossOrigin = 'anonymous';

    let colormap;
    if('values' in metadata['colormaps'][state.currVariable]) {
        colormap = metadata['colormaps'][state.currVariable];
    } else { // Is a level-based variable
        colormap = metadata['colormaps'][state.currVariable][metadata.levels[state.curriLvl]];
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

        let units = metadata.variables[state.currVariable].units || '(Unknown units)';
        info += `<br>${closestValue.toFixed(6)} ${units}`;

        if(units == 'K') {
            let celcius = closestValue - 273.15;
            info += `<br>(${celcius.toFixed(6)} °C)`;
        }

        L.popup()
            .setLatLng([lat, lon + deltaLon])
            .setContent(info)
            .openOn(map);
        state.popupLatLng = [lat, lon + deltaLon];
    }

    img.onerror = e => {
            console.error('Image load failed', e);
    };

    img.src = url;
}