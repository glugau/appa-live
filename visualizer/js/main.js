import { setupMap } from './mapSetup.js';

setupMap().then(({ map, metadata }) => {
    console.log('Map initialized successfully');
}).catch(error => {
    console.error('Failed to initialize map:', error);
});