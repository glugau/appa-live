// import * as zarr from "https://cdn.jsdelivr.net/npm/zarrita/+esm";

// let store = await zarr.tryWithConsolidated(
// 	new zarr.FetchStore("https://appa.nvidia-oci.saturnenterprise.io/2025-07-24T06Z_PT48H.zarr/")
// );

// let root = await zarr.open(store, { kind: "group" });
// let variable = await zarr.open(root.resolve("2m_temperature"), { kind: "array" });
// const region = await zarr.get(variable, [1, null, null])
// console.log(region)

export function generateTile(){}