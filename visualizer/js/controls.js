import { state } from './state.js';
import { showVariable } from './layerManager.js';

export function createVariableSelector(map, metadata) {
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
                state.currVariable = value;
                togglePressureSelector(map, metadata, metadata.variables[value].is_level);
                showVariable(map, metadata, state.currVariable, state.curriLvl);
            };

            select.onchange = e => runLogic(e.target.value);

            // Run logic on initial load
            setTimeout(() => runLogic(select.value), 0);

            return div;
        },

        onRemove: function(map) {}
    });
    return new VariableSelector({ position: 'topright' });
}

export function togglePressureSelector(map, metadata, show) {
    if(state.currPressureSelector && show) {
        return;
    }

    if(!state.currPressureSelector && !show){
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
                    state.curriLvl = metadata.levels.indexOf(+value);
                    showVariable(map, metadata, state.currVariable, state.curriLvl)
                };

                select.onchange = e => runLogic(e.target.value);

                // Run logic on initial load
                setTimeout(() => runLogic(select.value), 0);

                return div;
            },

            onRemove: function(map) {}
        });
        state.currPressureSelector = new PressureSelector({ position: 'topright' })
        map.addControl(state.currPressureSelector);
    } else {
        map.removeControl(state.currPressureSelector);
        state.currPressureSelector = null;
    }
}