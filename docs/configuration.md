# Konfigurace

Filtrování se aktivuje na konkrétní stránce klíčem `filters:` v konfiguraci `pages`. Bez tohoto klíče plugin stránku ignoruje.

## Kompletní schema

```yaml
site:
  pages:
    vsechna_mista:
      template: vsechna_mista.html
      path: /vsechna-mista.html
      paginate_by: 20                   # volitelně přepíše globální paginate_by pro JS stránkování
      filters:
        fields:                         # POVINNÉ (viz níže)
          - slug
          - nazev
          - umisteni
          - pribeh
          - stitky
          - stitky_slug
          - vytvoreno
          - id_radku
          - typ
          - typ_slug
        card_template: _karta_filter.html   # POVINNÉ
        facets: true                    # volitelně: fasetový režim
        facets_mode: hide               # hide | disable (default: hide)
        dimensions:
          typ:
            label: Typ                    # POVINNÉ — text v triggeru
            type: select                  # select | multiselect
          stitky:
            label: Štítek
            type: multiselect
            many: true                    # sloupec obsahuje JSON pole
          datace:
            label: Datace
            type: select
            url: "/obdobi/{slug}.html"    # explicitní URL šablona (nepovinná)
```

## Klíče

### `fields` (list, povinné)

Určuje, která pole záznamu se dostanou do filter JSONu (`/jsons/<page-stem>-filter.json`). Musí obsahovat:

- **Pole potřebná pro filtrování**: sloupce s daty, nad kterými se filtruje. Pro dimenzi s `many: true` (JSON pole tagů) potřebuješ jak samotný sloupec (`stitky`), tak i jeho slug lookup (`stitky_slug`), protože JS převádí hodnoty na slugy přes tento lookup.
- **Pole potřebná pro rendering karty**: vše, co použije `data-field` v [card templatu](card-template.md) — např. `slug`, `nazev`, `umisteni`, `pribeh`, `id_radku`, `vytvoreno`.
- **Slug varianty**: pro dimenze s `many: false` obvykle potřebuješ `{dim}_slug` sloupec (JS ho preferuje před hodnotou pro matching).

Pokud pole není v `fields`, není ve filter JSONu a JS ho nebude umět nabídnout / zobrazit.

### `card_template` (string, povinné)

Cesta k Jinja2 partial souboru, který renderuje jednu kartu. Použije se jako obsah `<template id="card-template">` — plugin ho pre-renderuje s prvním záznamem (`filtered[0]`) a JS ho klonuje pro každý filtrovaný záznam.

Detaily: [card-template.md](card-template.md).

### `dimensions` (dict, povinné)

Slovník filtračních dimenzí. Klíč = název sloupce v hlavní tabulce DB.

Pro každou dimenzi:

| Klíč | Typ | Popis |
|---|---|---|
| `label` | string | Zobrazovaný název (např. „Typ", „Štítek") |
| `type` | `select` \| `multiselect` | UI hint |
| `many` | bool | `true` pokud sloupec obsahuje JSON pole hodnot (jako tagy) |
| `url` | string | URL šablona s `{slug}` placeholderem pro `href` pill/checkbox elementu (viz níže) |
| `sort` | string | Pořadí hodnot v seznamu — preset (`count` \| `alpha`) nebo explicitní multi-column (`-count,alpha`); viz [Sortování](#sortování) |

#### `type: select` vs `multiselect`

Určuje default UI chování — `select` v UI dovolí max 1 aktivní hodnotu (radio-like), `multiselect` 0—n (checkbox-like). Vlastní widget si toto pravidlo vynucuje sám; plugin s tím jen informativně pracuje.

**Filtrovací logika je vždy OR uvnitř dimenze** — bez ohledu na `type` platí, že vyfiltrují se záznamy odpovídající kterékoliv aktivní hodnotě.

#### `many: true`

Použij, když sloupec obsahuje JSON pole (typicky tagy):

```
stitky column:      '["baroko","hrbitov"]'
stitky_slug column: '{"baroko":"baroko","hrbitov":"hrbitov"}'
```

Plugin toto detekuje a při načítání distinct hodnot vezme unikátní prvky napříč všemi záznamy. Vyžaduje existenci sloupce `{dim}_slug` s JSON objektem mapujícím hodnota → slug (stejná konvence jako existující category stránky v krizky).

Pro JSON pole se `count` u každé hodnoty počítá jako počet záznamů obsahujících tuto hodnotu (ne celkový výskyt).

#### `url`

URL šablona s `{slug}` placeholderem — použije se jako `href` na pill/checkbox elementu. Ovlivňuje:

- No-JS: klik navede na tuto URL (typicky statická category stránka)
- S JS: `href` zůstává platný pro middle-click / open-in-new-tab
- SEO: crawler najde odkazy na category stránky

Pokud není uveden, plugin **automaticky** hledá matching category stránku v `pages:` (viz [Auto-detekce URL](#auto-detekce-url) níže). Pokud nic nenajde, pill nemá `href` (jen `#`).

## Sortování

`sort` klíč u dimenze určuje pořadí hodnot ve widgetu. Podporovány jsou dva formáty:

### Presety (shorthand)

- **`count`** (default) — nejčastější hodnota nahoře; při shodě počtu abecedně (alias pro `-count,alpha`)
- **`alpha`** — abecedně ASC, locale-friendly (diakritika se ignoruje, takže "čáp" se řadí mezi c-slova, ne za "z")

### Explicitní multi-column

Comma-separated seznam polí s volitelným `-` prefixem pro DESC. Podporovaná pole: `count`, `alpha`.

```yaml
sort: "-count,alpha"     # count DESC, alpha ASC tiebreaker (== preset "count")
sort: "alpha,-count"     # alpha ASC primární, count DESC tiebreaker
sort: "-alpha"           # alpha DESC (Z→A)
sort: "count"            # count ASC (bez `-` prefixu)
```

> Kvůli YAML doporučuji hodnotu s `-` prefixem citovat (`"-count"` místo `-count`), byť oba tvary fungují.

### Per-dimenze

Různé dimenze mohou mít různé strategie:

```yaml
dimensions:
  typ:
    label: Typ
    type: select
    sort: alpha              # ~10 kategorií — abecedně se dobře prochází
  stitky:
    label: Štítek
    type: multiselect
    many: true
    sort: count              # ~50 tagů — populární nahoře pomůže exploraci
  datace:
    label: Datace
    type: select
    sort: "-alpha,-count"    # od nejnovější k nejstarší (např. „2020s", „2010s"...)
```

Neznámé pole vyhodí `ValueError` při buildu — chytí typo.

## Auto-detekce URL

Když `url` v konfiguraci dimenze chybí, plugin projde `pages:` a hledá stránku, kde:

- `page_cfg["category"] == dim_key`, A ZÁROVEŇ
- `page_cfg.get("many", False) == dim_cfg.get("many", False)`

Z odpovídající stránky vezme `path` template a nahradí `{{ category.slug }}` doslovným `{slug}`. Priorita:

1. Explicitní `url:` v dimension configu — nejvyšší
2. Auto-detekce z `pages`
3. Prázdný string — pill bude jen tlačítko bez odkazu

**Příklad:**

```yaml
pages:
  kategorie:                              # ← plugin ji najde pro dim `typ`
    category: typ
    path: "/kategorie/{{ category.slug }}.html"
    template: kategorie.html
  stitek:                                 # ← plugin ji najde pro dim `stitky` (many)
    category: stitky
    many: true
    path: "/stitek/{{ category.slug }}.html"
    template: stitek.html
  vsechna_mista:
    filters:
      dimensions:
        typ: {label: Typ, type: select}                        # url = /kategorie/{slug}.html
        stitky: {label: Štítek, type: multiselect, many: true} # url = /stitek/{slug}.html
```

## Facets (dynamické počty a skrývání)

Když `facets: true`, plugin dynamicky přepočítá počty u každé hodnoty na základě aktuálně aktivních filtrů z ostatních dimenzí. Hodnoty, které by po aplikaci vedly k prázdnému výsledku, se skryjí (nebo znepřístupní podle `facets_mode`).

**Pravidlo self-exclusion**: při výpočtu counts pro dimenzi X se aplikují všechny ostatní filtry, ale ne filtr na X. Uživatel tak vidí "kolik výsledků bych měl, kdybych přepnul hodnotu v X".

**`facets_mode`**:
- `hide` (default) — hodnoty s count = 0 se skryjí (`hidden`), dimenze s nulou dostupných hodnot se znepřístupní
- `disable` — hodnoty s count = 0 se šedě zabarví (třída `is-disabled`, `aria-disabled`, `pointer-events: none`), zůstávají viditelné

Když je aktivní hodnota jako součást URL, ale nemá záznamy pod ostatními filtry (count = 0), dimenze zůstane přístupná, aby ji uživatel mohl odebrat — jinak by byl v pasti.

Vlastnosti přepočtu:
- Cost per update: O(dimensions × records × avgSlugsPerRecord) — pro 600 záznamů a 3 dimenze pár ms, u velkých datasetů (10k+) zvažuj optimalizace
- Facet counts jsou vysílány ve `krizky-filters:update` event (`detail.facets`), takže vlastní widgety je mohou zobrazovat vlastním způsobem

Viz [javascript.md](javascript.md#facets) pro detaily JS API.

## Kontext fotek

Plugin využívá existující foto konfiguraci `sources.photos.base_url` pro sestavování URL thumbnailů v JS-renderovaných kartách. Nemusíš nic konfigurovat navíc — stačí, aby projekt měl fotky nastavené standardní krizky konvencí (číslo řádku, `{padded_id}_{size}.{format}`).

Konkrétní `size` a `format` se určují **v šabloně karty** (viz [card-template.md](card-template.md)), ne v configu — jsou to vizuální detaily náležející k designu karty.

## Globální nastavení

Plugin respektuje existující site config:

| Klíč | Default | Použití |
|---|---|---|
| `site.paginate_by` | 10 | Počet záznamů na stránku |
| `site.pagination_window` | 2 | Stránky okolo aktuální v paginátoru |
| `site.pagination_boundary` | 1 | Stránky vždy zobrazené na krajích |

Přepis per-page:

```yaml
pages:
  vsechna_mista:
    paginate_by: 24
    filters: { ... }
```

## Souborový výstup

Pro každou stránku s `filters:` plugin vygeneruje:

- `<output>/jsons/<page-stem>-filter.json` — pole záznamů s poli uvedenými v `filters.fields`
- `<output>/krizky-filters/filters.css` — CSS pluginu (kopírováno idempotentně při každém buildu)
- `<output>/krizky-filters/filters.js` — JS pluginu
