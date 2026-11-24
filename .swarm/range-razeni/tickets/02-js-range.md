---
id: "02"
slug: js-range
title: Dimenze range ve filters.js a zpřístupnění čistých funkcí testům
status: pending
depends_on: []
files:
  - krizky_filters/assets/krizky-filters/filters.js
  - tests/js/load-filters.mjs
  - tests/js/range.test.mjs
  - docs/javascript.md
attempts: 0
pr: ""
---

## Cíl
Oživí dimenzi `type: range` v prohlížeči podle specifikace `.swarm/range-razeni/spec.md`, část 1 „JS“, a zavede mechanismus z části 3, kterým se čisté funkce z `filters.js` dostanou do testů `node --test`. Python strana (config v `#filter-config`, šablona s poli `[data-filter-range]`) vzniká souběžně v tiketu 01. Kontrakt je ve specifikaci: dimenze má v `#filter-config` `{label, type: "range", unit, step}`, pole mají `data-filter-range="min|max"` a `data-filter-dimension="<dim>"`. Řazení záznamů řeší tiket 03, který naváže na mechanismus z tohoto tiketu.

## Akceptační kritéria
Zpřístupnění testům (rozhodnutí plánovače k části 3):
- V prohlížeči se dál načítá jediný `filters.js`, `inject_body_end` se nemění.
- Nové čisté funkce jsou deklarace funkcí (`function x() {}`) uvnitř stávajícího IIFE. Hned za `'use strict'`, ještě před bootstrapem (`getElementById('filter-config')`), je IIFE vystaví jako `globalThis.krizkyFiltersPure = Object.freeze({ ... })` s komentářem, že jde o čisté funkce pro testy, ne o stabilní API.
- Stávající funkce se nepřesouvají ani nepřepisují. Mění se jen tam, kde do nich přibývá větev pro `range` (`parseUrlState`, `matchesDim`, `computeFacets`, `updateActiveList`, `filterAndRender`, bootstrap po načtení dat).
- `tests/js/load-filters.mjs` načte `filters.js` bez DOM (stub `document` s `getElementById: () => null` a `documentElement.classList.remove`, IIFE pak skončí v bootstrapu) a vrátí `globalThis.krizkyFiltersPure`. Testy `tests/js/*.test.mjs` ho importují.
- ESLint, Prettier ani `scripts/verify` se nemění a procházejí.

Čisté funkce (názvy jsou doporučené, tiket 03 je bude používat):
- `toNumber(value)`: číslo pro konečné `number` a pro neprázdný číselný řetězec (`"52.5"`), jinak `null` (`null`, `undefined`, `""`, `"abc"`, `true`, `NaN`, `Infinity`).
- `parseRangeValue(raw)`: `{min, max}` (každá mez číslo nebo `null`), nebo `null` pro neplatnou hodnotu. Platné jsou `3000000-5000000`, `3000000-`, `-5000000`, `52.5-60`. Neplatné jsou `abc`, `1-2-3`, `-`, `""` a záporná čísla. Když je min > max, meze se prohodí.
- `serializeRange({min, max})`: kanonický tvar `3000000-5000000`, `3000000-`, `-5000000`, bez nadbytečných nul a mezer (`"003000000-"` po parse a serializaci dá `"3000000-"`). Pro obě meze `null` vrací `""`.
- `matchesRange(value, range)`: meze včetně, hodnota přes `toNumber`. Při aktivním rozsahu `null`, chybějící pole i nečíselná hodnota neprojdou.
- `rangeExtent(records, field)`: `{min, max}` přes záznamy s číselnou hodnotou pole (přes `toNumber`), nebo `null` pro prázdný seznam nebo seznam bez čísel.

Chování na stránce (část 1 „JS“ specifikace):
- `parseUrlState`: pro `range` parsuje parametr přes `parseRangeValue`. Platnou hodnotu uloží jako jeden kanonický řetězec v `Set` (jako textová dimenze), neplatnou ignoruje. `serializeState` a tvar `activeState` v `krizky-filters:update` se nemění.
- `matchesDim`: pro `range` parsuje řetězec ze stavu a volá `matchesRange(record[dim], range)`. Dimenze bez aktivního rozsahu pustí každý záznam. Rozsah se tak účastní `matchesFilter` i `matchesAllExcept`.
- `computeFacets` přeskočí `range` stejně jako `text`.
- Pole `[data-filter-range][data-filter-dimension]`: `change` hned, `input` s debounce 300 ms. Hodnoty obou polí dimenze se převedou na kanonický řetězec (přes `parseRangeValue`/`serializeRange`). Obě prázdné nebo neplatné → dimenze není aktivní (`state.delete`). Pak `currentPage = 1`, `updateUrl()`, `filterAndRender()`.
- Při načtení a po `popstate` se pole vyplní ze stavu. Pole, které má fokus, se nepřepisuje (vzor `syncTextInputs`).
- Placeholdery polí `min`/`max` = `rangeExtent` přes záznamy, které projdou `matchesAllExcept(r, dim)` (s fasetami), nebo přes všechny záznamy (bez fasetů). Když takový záznam není, placeholdery jsou prázdné. Přepočítají se při každém `filterAndRender`.
- Chip v `[data-filter-active-list]`: „Cena: 3 000 000–5 000 000 Kč“, „Cena: od 3 000 000 Kč“, „Cena: do 5 000 000 Kč“ (label z configu, čísla přes `toLocaleString(document.documentElement.lang || undefined)`, `unit` jen když není prázdný). Text jde do DOM jen přes `textContent`. Klik na chip odebere rozsah a pole se vyprázdní. `[data-filter-clear]` vyprázdní i rozsahy.
- Hlavičkový komentář `filters.js` vyjmenuje nový hook `[data-filter-range="min|max"][data-filter-dimension]`.
- `docs/javascript.md`: range ve stavu a v URL (sekce „URL state“), fasety pro range (placeholdery), `range` v `#filter-config` (`unit`, `step`), nový hook v „Data-attribute hooks“, krátká poznámka o `globalThis.krizkyFiltersPure` (jen pro testy, není stabilní API).
- `scripts/verify` skončí s exit 0.

## Testy
Nejdřív `tests/js/load-filters.mjs` a selhávající `tests/js/range.test.mjs` (`node:test`, `node:assert/strict`), pak implementace:
1. `parseRangeValue` + `serializeRange` tabulkou (parametrize styl, smyčka nad polem případů): platné tvary, jen dolní a jen horní mez, prohozené meze (`5-3` → `3-5`), desetinné číslo (`52.5`), nadbytečné nuly, neplatné tvary (`abc`, `1-2-3`, `-`, `""`, `-5-`) → `null`.
2. `matchesRange`: meze včetně (hodnota rovná min i max projde), `null`, chybějící pole (`undefined`), číselný řetězec, nečíselný řetězec, jen dolní a jen horní mez.
3. `rangeExtent`: ignoruje `null` a nečíselné hodnoty, bere číselné řetězce, prázdný seznam → `null`, seznam bez čísel → `null`.
4. `toNumber`: tabulka hodnot z akceptačních kritérií.

## Poznámky
- Guidelines: `/Users/msgre/projects/muzeum/krizky/docs/guidelines/javascript.md` (IIFE + `'use strict'`, `const`, deklarace funkcí pro utility, bez `console.log`), `cross-language.md`, `security.md` (hodnoty z URL jen přes `textContent` a atributy, nikdy jako HTML).
- **TDZ:** testy volají funkce, i když IIFE skončí v bootstrapu. Nové čisté funkce proto nesmí sahat na `const`/`let` deklarované ve IIFE za bootstrapem (byly by v TDZ a volání by hodilo `ReferenceError`). Konstanty, které potřebují, deklaruj před exportem nebo uvnitř funkce. Deklarace funkcí (i stávající `sortKeyAlpha`) jsou hoistované a jsou v pořádku.
- **Načtení v testu:** `package.json` nemá `"type"`, takže `filters.js` je pro Node CommonJS. Nejjednodušší je nastavit stub `globalThis.document`, `await import(...)` souboru a přečíst `globalThis.krizkyFiltersPure` (stejný realm, `assert.deepStrictEqual` funguje). Při použití `node:vm` s novým kontextem pozor, že objekty z jiného realmu neprojdou `deepStrictEqual` kvůli prototypu.
- **ESLint:** node globály (`URL`, `process`) má jen `**/*.test.mjs`. V `tests/js/load-filters.mjs` je nepoužívej (cestu skládej přes `import.meta.url`, `fileURLToPath` z `node:url` a `node:path`), nebo si ověř, že `npx --no-install eslint --max-warnings 0 .` projde. Konfiguraci ESLint neměň.
- `input type="number"` vrací v `value` prázdný řetězec pro nečíselný vstup. Záporné číslo zadané ručně nepřejde `parseRangeValue`, dimenze pak není aktivní.
- Placeholder je číslo bez formátování (pole je `type="number"`).
- Debounce 300 ms je samostatná konstanta (stávající `TEXT_DEBOUNCE_MS` = 200 neměň).
- Selektory `[data-filter-value]` (pills, fasety, `reorderValues`) se rozsahových polí netýkají, ověř, že na ně nic nesáhne.
- Neměň `plugin.py`, šablony ani `docs/configuration.md` / `docs/widgets.md` (tiket 01). Řazení záznamů nepřidávej (tiket 03).

## Otázky
