// Minimal ambient declarations for the offline map stack. Both packages are
// runtime-only dependencies of the Intel workspace and ship without types.

declare module 'leaflet';

declare module 'topojson-client' {
	export function feature(topology: any, object: any): any;
	export function mesh(topology: any, object: any, filter?: any): any;
}

declare module 'world-atlas/countries-110m.json' {
	const value: any;
	export default value;
}
