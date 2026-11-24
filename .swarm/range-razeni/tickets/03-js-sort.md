---
id: "03"
slug: js-sort
title: Řazení záznamů ve filters.js
status: pending
depends_on: ["02"]
files:
  - krizky_filters/assets/krizky-filters/filters.js
  - tests/js/sort.test.mjs
  - docs/javascript.md
attempts: 0
pr: ""
---

## Cíl
Oživí řazení výsledků v prohlížeči podle specifikace `.swarm/range-razeni/spec.md`, část 2 „JS“, a doplní k tomu `docs/javascript.md`. Navazuje na tiket 02: používá jeho mechanismus `globalThis.krizkyFiltersPure`, loader `tests/js/load-filters.mjs` a funkci `toNumber`. Python strana (`sortRecords` v `#filter-config`, `<select data-filter-sort>` s volbami `""`, `cena`, `-cena`) vzniká v tiketu 01 podle stejného kontraktu ze specifikace.

## Akceptační kritéria
Čisté funkce (vystavené v `globalThis.krizkyFiltersPure` vedle funkcí z tiketu 02):
- `parseSortParam(raw, options)`: pro `cena` vrátí `{field: "cena", desc: false}`, pro `-cena` `{field: "cena", desc: true}`. Pro pole mimo `options` (seznam `{field, label}` ze `sortRecords.options`), prázdnou hodnotu, `null` a samotné `-` vrátí `null`.
- `compareSortValues(a, b, desc)`: `null`, `undefined` a prázdný (i jen bílý) řetězec jdou vždy na konec bez ohledu na `desc`. Dvě čísla nebo číselné řetězce (přes `toNumber`) se porovnávají číselně, ostatní přes stávající `sortKeyAlpha(String(v))`. `desc` obrací jen porovnání neprázdných hodnot.
- `sortRecords(records, sort)`: nová pole (vstup nemutuje), stabilní řazení podle `record[sort.field]` a `compareSortValues`. Pro `sort === null` vrátí záznamy ve vstupním pořadí.

Chování na stránce:
- Bez `config.sortRecords` (`null` nebo chybí) se nic nemění: žádný parametr v URL, žádné řazení, `sort: null` v události.
- Stav řazení je samostatná proměnná (ne v `state`), takže `activeState`, `updateClearButton` ani `[data-filter-clear]` se ho netýkají a `[data-filter-clear]` řazení neresetuje.
- `parseUrlState` čte parametr `sortRecords.param` přes `parseSortParam`. Neplatná hodnota se ignoruje (výchozí řazení).
- `serializeState` zapisuje řazení spolu s filtry (`?cena=...&sort=-cena`). Výchozí řazení parametr nemá. Odkazy stránkování (`pageHref`) tak řazení zachovají.
- `filterAndRender`: řazení se aplikuje na vyfiltrované záznamy před stránkováním. `krizky-filters:update` má v `detail` nový klíč `sort` (`"cena"`, `"-cena"` nebo `null`) a `filteredRecords` jsou v pořadí po seřazení. Ostatní klíče `detail` se nemění.
- `change` na `<select data-filter-sort>` nastaví řazení (hodnota `""` = výchozí), `currentPage = 1`, `updateUrl()`, `filterAndRender()`.
- Při načtení i po `popstate` se hodnota všech `[data-filter-sort]` nastaví podle stavu.
- Hlavičkový komentář `filters.js` vyjmenuje hook `[data-filter-sort]`.
- `docs/javascript.md`: klíč `sort` v ukázce a popisu `krizky-filters:update`, pořadí `filteredRecords` (po seřazení), parametr řazení v sekci „URL state“, `sortRecords` v ukázce `#filter-config`, hook `[data-filter-sort]` v „Data-attribute hooks“.
- `scripts/verify` skončí s exit 0.

## Testy
Nejdřív selhávající `tests/js/sort.test.mjs` (přes `tests/js/load-filters.mjs` z tiketu 02), pak implementace:
1. `parseSortParam` tabulkou: `cena`, `-cena`, neznámé pole, `""`, `null`, `-`.
2. `compareSortValues` a `sortRecords`: čísla (`2` před `10`), číselné řetězce (`"9.5"` před `"10"`), text s diakritikou (`"čáp"` mezi `"cap"` a `"dub"`, bez ohledu na velikost písmen), `null`, chybějící pole a `""` na konci vzestupně i sestupně, stabilita při shodě (záznamy se stejnou hodnotou si drží vstupní pořadí v obou směrech), `sortRecords` nemutuje vstupní pole a pro `null` vrací vstupní pořadí.

## Poznámky
- Guidelines: `/Users/msgre/projects/muzeum/krizky/docs/guidelines/javascript.md`, `cross-language.md` (klíče `sortRecords`, `param`, `options`, `field`, `label` jak je posílá Python), `security.md`.
- TDZ: nové čisté funkce nesmí sahat na `const`/`let` deklarované ve IIFE za bootstrapem (viz poznámka v tiketu 02). `sortKeyAlpha` je hoistovaná deklarace funkce a je v pořádku. Stávající funkce nepřesouvej ani nepřepisuj.
- Když je číselná jen jedna ze dvou hodnot, specifikace to neřeší. Porovnej obě jako text přes `sortKeyAlpha(String(v))` a napiš to do komentáře.
- Stabilita: `Array.prototype.sort` je v moderních enginech stabilní. Komparátor pro „prázdné na konec“ musí vracet 0 pro dvě prázdné hodnoty.
- Stávající `parseSort`, `sortWrappedByColumns` a `SORT_ALIASES` slouží k řazení hodnot ve filtru, ne záznamů. Neměň je a pojmenuj nové funkce tak, aby se s nimi nepletly.
- Kolizi `param` s klíčem dimenze hlásí Python varováním. V JS ji neřeš.
- Neměň `plugin.py`, šablony ani ostatní dokumentaci.

## Otázky
