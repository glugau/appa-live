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

function lngLatToTileXY(lon, lat, zoom) {
  const x = Math.floor(((lon + 180) / 360) * Math.pow(2, zoom));
  const y = Math.floor(
    (1 -
      Math.log(
        Math.tan((lat * Math.PI) / 180) + 1 / Math.cos((lat * Math.PI) / 180)
      ) /
        Math.PI) /
      2 *
      Math.pow(2, zoom)
  );
  return { x, y, z: zoom };
}

function lngLatToPixelInTile(lon, lat, zoom) {
  const scale = Math.pow(2, zoom) * 256;
  const x = ((lon + 180) / 360) * scale;
  const y =
    ((1 -
      Math.log(
        Math.tan((lat * Math.PI) / 180) + 1 / Math.cos((lat * Math.PI) / 180)
      ) /
        Math.PI) /
      2) *
    scale;
  return { x: Math.floor(x) % 256, y: Math.floor(y) % 256 };
}

function closestRgb(rgb, rgbArr) {
    let minDist = Infinity;
    let closestIndex = -1;
    for (let i = 0; i < rgbArr.length; i++) {
        const { r, g, b } = rgbArr[i];
        const dist = (r - rgb.r) ** 2 + (g - rgb.g) ** 2 + (b - rgb.b) ** 2;
        if (dist < minDist) {
        minDist = dist;
        closestIndex = i;
        }
    }
    return closestIndex;
}