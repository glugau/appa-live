import { state } from './state.js';

export function addLegend(map, metadata, variable, iLevel) {
    if (state.currLegend) {
        map.removeControl(state.currLegend);
    }
    
    state.currLegend = L.control({ position: 'bottomright' });
    state.currLegend.onAdd = function(map) {
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
        let units = metadata.variables[state.currVariable].units || '(Unknown units)';
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
    
    state.currLegend.addTo(map);
}