# JavaScript API

Plugin JS `filters.js` je čistý vanilla ES2020, žádné závislosti, spouští se jako IIFE. Neexportuje globální objekt — komunikuje s externím kódem přes **DOM (data-* atributy)** a **DOM events**.

## Custom event `krizky-filters:update`

Po každé změně filtru (a při inicializaci) plugin vysílá custom event na `document`:

```javascript
document.dispatchEvent(new CustomEvent("krizky-filters:update", {
  detail: {
    filtered: 61,               // počet záznamů po aplikaci filtrů
    total: 537,                 // celkový počet záznamů
    activeState: {              // aktivní filtry po dimenzích
      typ: ["kriz"],
      stitky: ["baroko", "hrbitov"]
    },
    facets: {                   // null když facets: false; jinak počty per dimension
      typ: { kriz: 61, socha: 3, ... },
      stitky: { baroko: 42, hrbitov: 19, ... }
    }
  }
}));
```

**Když to zapadá:**

- Custom widget potřebuje aktualizovat vlastní UI (combobox trigger label, chip lišta)
- Externí JS chce reagovat na změnu filtru (analytics, animace)
- Vlastní kód potřebuje sledovat počet filtrovaných výsledků

**Příklad — reaktivní chip lišta v combobox designu:**

```javascript
document.addEventListener("krizky-filters:update", (e) => {
  const { activeState } = e.detail;
  const chipContainer = document.querySelector("[data-my-chips]");
  chipContainer.innerHTML = "";
  for (const [dim, slugs] of Object.entries(activeState)) {
    slugs.forEach(slug => {
      const chip = document.createElement("button");
      chip.textContent = `${dim}: ${slug}`;
      chip.dataset.filterClearDim = dim;  // klik zruší celou dimenzi
      chipContainer.appendChild(chip);
    });
  }
});
```

Event se vysílá **po** interním překreslení karet a stránkování — DOM je v tu chvíli konzistentní se `state`.

## URL state

Plugin ukládá stav do URL — stejný formát jako server-side stránkování:

```
Základ:       /vsechna-mista.html
Stránka N:    /vsechna-mista-N.html
Filtry:       ?typ=kriz&stitky=baroko,hrbitov
Kombinace:    /vsechna-mista-2.html?typ=kriz&stitky=baroko
```

**Cesta** kóduje číslo stránky (path segment). **Query params** kódují filtry — jedna dimenze = jeden parameter, více hodnot = čárka.

Vlastnosti:
- Funguje browser back/forward (`popstate` listener)
- URL bookmarkovatelná — vstup s URL parametry rovnou aktivuje filtr
- Middle-click / open-in-new-tab funguje díky reálným `href` atributům na pill/pagination linkách
- Kompatibilní s no-JS (server má statické stránky `/vsechna-mista-N.html`, filtry v query se pak jen ignorují)

## Data-attribute hooks

Všechny hookovací atributy fungují přes **event delegation** nebo přes DOM query při rendu — dynamicky vložené elementy fungují stejně jako statické. Můžeš je přidat kamkoliv do stránky, ne jen do filter widgetu.

### Filter controls

| Atribut | Chování |
|---|---|
| `[data-filter-value="slug"][data-filter-dimension="dim"]` | Element funguje jako filter control. Click → toggle hodnoty ve state, aplikovat filtr. |
| `[data-filter-clear]` | Click → vyprázdnit všechny filtry. Element se skryje (`hidden`) když nic není aktivní. |
| `[data-filter-clear-dim="dim"]` | Click → vymazat jen tu dimenzi. Užitečné pro chip × tlačítko nebo per-dimension clear v combobox triggeru. |

### Status výstupy

| Atribut | Chování |
|---|---|
| `[data-filter-count-filtered]` | JS zapisuje počet filtrovaných záznamů jako `textContent` |
| `[data-filter-count-total]` | JS zapisuje celkový počet |
| `[data-filter-count]` | Alternativa — původní textový obsah slouží jako template. JS nahradí `{filtered}` a `{total}`. |
| `[data-filter-active-list]` | JS renderuje `<button class="filter-chip">` per aktivní hodnotu. Klik na chip = odebrat hodnotu. |

**Příklad počítadla:**

```html
<p data-filter-count>Zobrazeno {filtered} z {total} míst</p>
```

Při inicializaci `data-filter-count-orig` uchová původní text, JS pak jen nahrazuje placeholdery.

### Grid & paginace

| Atribut | Chování |
|---|---|
| `[data-filter-grid]` | Kontejner karet — JS ho vyprázdní a naplní klonovanými `<template>` elementy |
| `[data-filter-pagination]` | Kontejner stránkování — JS ho naplní `<nav class="pagination">` HTML |
| `[data-static-pagination]` | Wrapper okolo server-rendered paginátoru — JS ho skryje, když převezme kontrolu |

### Card template

Cíl je `<template id="card-template">`, obsah renderovaný z partial souboru zadaného v `filters.card_template`. JS klonuje jeho `content` per záznam.

Podrobnosti: [card-template.md](card-template.md).

## Facets

Aktivují se v configu (`filters.facets: true`). Po každém updatu filtru:

1. Pro každou dimenzi X spočítá `subset` = záznamy odpovídající všem AKTIVNÍM filtrům KROMĚ filtru na X
2. Pro každou hodnotu V v X spočítá, kolikrát se V vyskytuje v `subset`
3. Aktualizuje DOM: každý `[data-facet-count]` element uvnitř `[data-filter-value]` dostane nový count
4. Podle `facetsMode` skryje/znepřístupní hodnoty s count = 0
5. Celé dimenze bez dostupných hodnot označí jako `is-disabled` (kromě dimenze s aktivní hodnotou — tam musí zůstat cesta ven)
6. **Přerovná DOM elementy** podle `sort` klíče dimenze — se stejnou logikou jako Python side (viz [configuration.md#sortování](configuration.md#sortování)). Při shift ze static counts na facet counts se hodnoty automaticky přeuspořádají (např. `sort: -count,alpha` posune nejčastější dostupnou hodnotu na začátek). Pořadí drží stejný sort spec jako build-time — konzistentní s tím, co vidí uživatel bez JS.

**Data hooks pro facety:**

| Atribut | Chování |
|---|---|
| `[data-facet-count]` uvnitř `[data-filter-value]` | JS zapisuje aktualizovaný count |
| `[data-combobox]` / `.fbar-dim` | JS přepíná `is-disabled` třídu podle dostupnosti |
| `[data-combobox-option]` (nebo `[data-filter-value]` samotný když není zabaleno) | JS přepíná `hidden` (mode: hide) nebo `is-disabled` (mode: disable) |

**Vlastní widget s facetami:**

Poslouchej `krizky-filters:update` event a čti `e.detail.facets[dim][slug]`. Můžeš úplně bypassovat plugin DOM update tím, že vlastní widget nepoužívá standardní hierarchie — plugin update je pak "best effort" a nic nerozbije.

```javascript
document.addEventListener("krizky-filters:update", (e) => {
  const facets = e.detail.facets;
  if (!facets) return;  // facets not enabled
  // Update your own UI here
  for (const [dim, counts] of Object.entries(facets)) {
    console.log(`Dim ${dim}:`, counts);
  }
});
```

## Text dim (fulltextové hledání)

`type: text` dimenze je speciální případ. Chování:

- **State**: `state.get(dim)` = `Set([queryString])` — jednoprvková množina drží dotaz jako string (pro konzistenci se zbytkem architektury)
- **URL**: `?q=xxx` bez comma-splittingu (query může obsahovat čárku, plugin ji nerozsekne)
- **Filter logika**: `normalizeText(record[field]).includes(normalizeText(query))` pro každé pole v `searchFields`
- **Normalizace**: `String.normalize("NFKD")` + strip combining chars → diakritika-agnostic, case-insensitive
- **Debounce**: 200 ms (konstanta `TEXT_DEBOUNCE_MS`)
- **Neúčastní se**: facet compute, DOM reorder, `updateFilterStates`

**Data-atribut hooks pro text dim:**

| Atribut | Chování |
|---|---|
| `[data-filter-text-dimension="dim"]` | Input element — JS připne `input` listener s debouncem, čte `input.value` |

Sync z URL do inputu funguje automaticky (`syncTextInputs` volané z `filterAndRender`). Aktivní element (focused) se neaktualizuje, aby uživatelův typing nebyl přerušen.

**Vlastní text widget** může být cokoliv — `<input>`, `<textarea>`, dokonce více inputů s různými dimenzemi. Musí mít `data-filter-text-dimension` a číst jeho hodnotu přes property `.value`.

## `#filter-config` script tag

Plugin injektuje do stránky JSON s konfigurací filtru:

```html
<script type="application/json" id="filter-config">
{
  "jsonUrl": "/jsons/vsechna-mista-filter.json",
  "basePath": "/vsechna-mista.html",
  "photosBaseUrl": "https://cdn.example.com",
  "pageSize": 24,
  "gridSelector": "[data-filter-grid]",
  "window": 2,
  "boundary": 1,
  "dimensions": {
    "typ": {"label": "Typ", "type": "select"},
    "stitky": {"label": "Štítek", "type": "multiselect", "many": true}
  }
}
</script>
```

Custom JS to může přečíst pro vlastní účely (např. combobox JS potřebuje znát seznam dimenzí a jejich labely). Nikdy se do konfigurace nezapisuje z JS — je to input pro plugin.

## Vlastní widget — pattern

Když chceš vlastní filter widget (combobox, slider, atd.), postup je:

**1. Přebij `_filter_widget.html`** — vlastní HTML struktura obsahující elementy s `data-filter-value` a `data-filter-dimension`.

**2. Napiš vlastní JS** pro UI interakce (open/close dropdown, search filtering, apod.).

**3. Poslouchej `krizky-filters:update`** — aktualizuj UI na základě `e.detail.activeState`.

**Klíčová pravidla:**

- Nikdy nemanipuluj přímo se `state` pluginu — použij click na `[data-filter-value]` (přidat) nebo `[data-filter-clear-dim]` (odebrat).
- Neinjektuj filtry přímo do URL — plugin to řeší sám.
- Neblokuj event propagaci na filter control elementech — plugin je odchytává na document úrovni.

## Debugging

Kontroly v browser konzoli:

```javascript
// Config injektovaný do stránky
JSON.parse(document.getElementById("filter-config").textContent);

// Aktuální URL params
new URLSearchParams(location.search);

// Poslední update event (uložíš si sám)
document.addEventListener("krizky-filters:update", (e) => {
  window.lastUpdate = e.detail;
  console.log("filter update:", e.detail);
});

// Skutečné data v filter JSONu
fetch(JSON.parse(document.getElementById("filter-config").textContent).jsonUrl)
  .then(r => r.json())
  .then(data => window.filterData = data);
```
