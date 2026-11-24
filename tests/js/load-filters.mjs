// Načte filters.js bez DOM a vrátí čisté funkce, které IIFE vystavuje v
// globalThis.krizkyFiltersPure. Bez elementu #filter-config skončí IIFE v bootstrapu.
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const filtersPath = resolve(here, '../../krizky_filters/assets/krizky-filters/filters.js');

globalThis.document = {
  getElementById: () => null,
  documentElement: { classList: { remove: () => {} } },
};

await import(pathToFileURL(filtersPath).href);

export const pure = globalThis.krizkyFiltersPure;
