---
id: "02"
slug: js-filter-class-lifecycle
title: filters.js odebírá třídu filter-js při selhání a zachová text napsaný před načtením
status: pending
depends_on: []
files:
  - krizky_filters/assets/krizky-filters/filters.js
  - docs/javascript.md
attempts: 0
pr: ""
---

## Cíl
Inline skript v `<head>` (tiket 01) nastaví na `<html>` třídu `filter-js` a CSS podle ní zobrazí ovládání s atributem `data-filter-js-only`. Když `filters.js` filtrování neoživí, musí třídu odebrat, aby se nefunkční ovládání skrylo a stránka zůstala ve statické podobě. Ovládání je vidět hned při vykreslení, takže uživatel může psát do textového hledání ještě před načtením dat a jeho text se nesmí ztratit. Viz specifikace `.swarm/js-only-widget/spec.md`, část 2 (JS) a část 4 (`docs/javascript.md`).

## Akceptační kritéria
- `filters.js` odebere třídu `filter-js` z `document.documentElement` ve všech třech případech:
  - chybí `#filter-config`, nebo jeho obsah nejde naparsovat,
  - na stránce není mřížka (`document.querySelector(gridSelector)` vrátí `null`),
  - selže načtení nebo parsování JSONu (dnešní `.catch`).
- Text, který je v `[data-filter-text-dimension]` inputu (s platnou textovou dimenzí) v okamžiku načtení dat, se po načtení použije. Má přednost před hodnotou z URL, nastaví se do `state` a promítne se do filtru i do URL. Prázdný input hodnotu z URL nepřebíjí.
- Hlavičkový komentář `filters.js` (seznam „UI hook points“) obsahuje `[data-filter-js-only]` s krátkým popisem.
- Název třídy je přesně `filter-js` a atributu přesně `data-filter-js-only` (`cross-language.md`). Třídu drž v jedné konstantě.
- `docs/javascript.md`: v sekci „Data-attribute hooks“ je nový háček `data-filter-js-only` a je popsané, kdy `filters.js` třídu `filter-js` odebere (tři případy výše) a že se stránka pak chová staticky. Je popsané i převzetí textu napsaného před načtením dat a známé omezení: když se `filters.js` vůbec nenačte, třídu nikdo neodebere.
- `scripts/verify` skončí s exit 0 (ESLint, Prettier).

## Testy
- Podle `CLAUDE.md` se kód závislý na DOM netestuje a stávající kód se kvůli testům nepřepisuje. Všechny změny jsou na DOM závislé, takže nový JS test nevzniká. Ověření je pohledem do diffu a přes `scripts/verify`.
- Pokud by vznikla čistá pomocná funkce (např. výběr hodnoty: text z inputu vs. hodnota z URL), můžeš ji otestovat přes `node --test` v `tests/js/*.test.mjs`. Není to povinné a kvůli tomu nerozbíjej IIFE.

## Poznámky
- Guidelines: `/Users/msgre/projects/muzeum/krizky/docs/guidelines/javascript.md` (IIFE + `'use strict'`, `const`, bez `console.log`), `cross-language.md`, `docs-sync.md`.
- Dnešní `.catch` na konci řetězce `fetch(...).then(...)` zachytí i výjimky z inicializace v `.then`. I v tom případě je odebrání třídy správné.
- Pozor na `syncTextInputs()`: přepíše hodnotu nefokusovaného inputu hodnotou ze `state` (z URL). Text napsaný před načtením je proto potřeba přečíst a vložit do `state` po `parseUrlState()` a před prvním `filterAndRender()`/`syncTextInputs()`. Jinak se ztratí, když uživatel mezitím input opustí.
- `updateUrl()` používá `history.pushState`. Zvaž, jestli při převzetí textu po načtení nepřidá zbytečný záznam do historie. Rozhodnutí krátce okomentuj v kódu.
- Ukaž i tlačítko pro vymazání (`updateTextClearVisibility`), pokud input obsahuje převzatý text.
- Neměň `filters.css`, šablony, `plugin.py` ani `docs/widgets.md`, patří tiketu 01. CSS pravidlo `html:not(.filter-js) [data-filter-js-only]` a inline skript přidává tiket 01. Tento tiket má smysl i samostatně, protože odebrání neexistující třídy nic nerozbije.
- Generování widgetu v JS a čekání na data před zobrazením ovládání jsou ve specifikaci zamítnuté.

## Otázky
