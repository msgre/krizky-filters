# Widgety

Plugin dodává výchozí filter widget jako soubor Jinja2 šablon. Každý projekt může kteroukoliv z nich přebít umístěním souboru se stejným jménem do vlastního `templates/`.

## Šablony pluginu

| Šablona | Účel |
|---|---|
| `_filter_widget.html` | Dispatcher — iteruje dimenze a deleguje na per-type šablony |
| `_filter_widget_select.html` | Widget pro `type: select` |
| `_filter_widget_multiselect.html` | Widget pro `type: multiselect` |
| `_filter_card_template.html` | Wrappuje card partial do `<template id="card-template">` |

Loading order Jinja2 loaderu: `project templates/` → `plugin templates/` → `krizky/templates/`. Cokoliv, co je v projektu, přebije plugin default.

## Přebít existující widget

Zkopíruj šablonu z pluginu do `templates/` svého projektu a uprav. Např. pro nový vzhled multiselect widgetu vytvoř `templates/_filter_widget_multiselect.html`.

Kontext, který má šablona k dispozici:

| Proměnná | Typ | Popis |
|---|---|---|
| `_dim_key` | string | Název dimenze (např. `typ`, `stitky`) |
| `_dim.label` | string | Label z configu |
| `_dim.type` | string | `select` \| `multiselect` |
| `_dim.many` | bool | Zda je sloupec JSON pole |
| `_dim["values"]` | list | Seznam hodnot |
| `_dim["values"][i].value` | string | Zobrazovaná hodnota (např. „Kříž") |
| `_dim["values"][i].slug` | string | Slug (např. „kriz") |
| `_dim["values"][i].url` | string | URL šablona s vyplněným slugem (nebo prázdný string) |
| `_dim["values"][i].count` | int | Počet záznamů s touto hodnotou (statický, spočítaný při buildu) |

Pořadí `_dim["values"]` je určeno klíčem `sort` v configu dimenze (default: count DESC, alpha ASC tiebreaker). Podrobnosti [configuration.md#sortování](configuration.md#sortování).

> **Pozor:** `values` je klíč slovníku, ne atribut, protože `_dim.values` v Jinja2 koliduje s built-in `.values()` metodou dict. Vždy `_dim["values"]`.

## Přidat nový typ widgetu

Dispatcher `_filter_widget.html` renderuje `{% include "_filter_widget_" ~ _dim.type ~ ".html" %}` — přidání nového typu tedy znamená:

1. Vytvoř nový soubor `templates/_filter_widget_boolean.html` (nebo jiný typ)
2. V configu použij `type: boolean` u dimenze

**Příklad — boolean widget (single toggle):**

```jinja2
{# templates/_filter_widget_boolean.html #}
<div class="filter-toggle">
  {% for _v in _dim["values"] %}
  <a href="{{ _v.url or '#' }}"
     class="toggle-btn"
     data-filter-value="{{ _v.slug }}"
     data-filter-dimension="{{ _dim_key }}"
     role="checkbox">
    {{ _v.value }}
  </a>
  {% endfor %}
</div>
```

Klíčové: jakýkoliv element s `data-filter-value` a `data-filter-dimension` funguje jako filter control — JS na něj automaticky připne click handler, přepne `pill--active` class podle stavu a integruje ho do URL state.

## Minimální kontrakt widget šablony

Aby JS uměl widget ovládat, musí obsahovat elementy s dvojicí atributů:

```
data-filter-value="{slug}"
data-filter-dimension="{dim_key}"
```

To je vše. JS:

- Připne click listener → intercepuje navigaci, přepíná hodnotu ve state, aktualizuje URL
- Přepíná `pill--active` třídu podle aktivního stavu (CSS si stylizuješ, jak chceš)
- Nastavuje `aria-pressed` atribut

Widget může být cokoliv: pilulka, checkbox, combobox item, slider option, radio input — hlavně ať má výše zmíněné atributy.

## Text widget

Pro `type: text` (fulltextové hledání) plugin dodává default `_filter_widget_text.html` — jednoduchý `<input type="search">` s data-atributem. Kontrakt widgetu:

```html
<input type="search"
       data-filter-text-dimension="{dim_key}"
       placeholder="{label}">
```

JS napojí `input` event s debounce 200 ms, aktualizuje state a URL. Widget nemá dropdown, seznam ani `[data-filter-value]` elementy.

**Přizpůsobení:**

- Přebij `_filter_widget_text.html` ve svém `templates/` a přidej CSS třídy / prvky dle designu
- Text dim nepotřebuje být uvnitř comboboxu — když máš dispatcher `_filter_widget.html`, který wrapuje ostatní dimenze do combobox struktury, pro text branch větev:

```jinja2
{% for _dim_key, _dim in _dims.items() if not _dim_key.startswith('_') %}
  {% if _dim.type == "text" %}
    {% include "_filter_widget_text.html" %}
  {% else %}
    <div class="fbar-dim" data-combobox ...>
      {% include "_filter_widget_" ~ _dim.type ~ ".html" %}
    </div>
  {% endif %}
{% endfor %}
```

**Kontext v šabloně** (parciální `_filter_widget_text.html`):

| Proměnná | Popis |
|---|---|
| `_dim_key` | Název dimenze — MUSÍ jít do `data-filter-text-dimension` |
| `_dim.label` | Text pro placeholder / aria-label |
| `_dim["values"]` | Prázdný list (text dim nemá diskrétní hodnoty) |

## Combobox pattern

Combobox (dropdown s vyhledáváním) není součástí pluginu, protože jeho open/close/search logika je čistě UI záležitost projektu. Plugin ale dodává **event `krizky-filters:update`**, který combobox JS potřebuje pro aktualizaci trigger tlačítka.

Postup:

1. Přebij `_filter_widget.html` — místo pill lišty vyrenderuj combobox trigger + dropdown per dimenzi
2. Napiš vlastní JS handling open/close/search
3. Odchytávej `krizky-filters:update` event a aktualizuj trigger label podle `detail.activeState[dim_key]`

Kompletní příklad combobox implementace: viz template soubory v `temp/templates/` demo projektu (`_filter_widget.html`, `_filter_widget_select.html`, `_filter_widget_multiselect.html`, `_filter_combobox_js.html`).

## Layout widgetu — data attributes hooks

Kromě filter controls dodává plugin i JS hooky pro doplňkové elementy widgetu:

| Atribut | Účel |
|---|---|
| `[data-filter-clear]` | Tlačítko „Vymazat vše" — JS na něj připne click handler, který vyprázdní stav |
| `[data-filter-clear-dim="typ"]` | Tlačítko „Vymazat jednu dimenzi" — vymaže jen dimenzi `typ` |
| `[data-filter-active-list]` | Kontejner, do kterého JS vkládá `<button class="filter-chip">` za každou aktivní hodnotu |
| `[data-filter-count-filtered]` | Element, do kterého se zapisuje počet filtrovaných záznamů |
| `[data-filter-count-total]` | Element, do kterého se zapisuje celkový počet záznamů |
| `[data-filter-count]` | Alternativa — element se šablonou `{filtered}`/`{total}` (JS nahradí placeholdery) |
| `[data-filter-grid]` | Kontejner, do kterého JS renderuje karty |
| `[data-filter-pagination]` | Kontejner pro JS stránkování (JS ho naplní) |
| `[data-static-pagination]` | Wrapper okolo statického paginátoru — JS ho skryje, když aktivně stránkuje |
| `[data-facet-count]` | (Facety) Element uvnitř `[data-filter-value]` — JS zapisuje aktualizovaný count |
| `[data-combobox]` s `[data-combobox-dim="X"]` | JS přepíná `is-disabled` třídu, když dimenze nemá dostupné hodnoty (facet mode) |

Detaily [javascript.md](javascript.md).

## Facet-aware widget

Když je v configu `filters.facets: true`, plugin JS po každé změně filtru:

- Přepíše text v `[data-facet-count]` element uvnitř každého `[data-filter-value]` na aktuální dynamický count
- Podle `facets_mode` skryje (`hidden` + `data-facet-hidden` atribut) nebo znepřístupní (`is-disabled` třída + `aria-disabled`) hodnoty s count = 0
- Přidá `is-disabled` třídu na `[data-combobox]` kontejnery bez dostupných hodnot

**Widget šablona pro facety** — přidej `data-facet-count` atribut ke count elementu:

```jinja2
<a class="fbar-item"
   data-filter-value="{{ _v.slug }}"
   data-filter-dimension="{{ _dim_key }}">
  <span class="fbar-item-label">{{ _v.value }}</span>
  <span class="fbar-item-count" data-facet-count>{{ _v.count }}</span>
</a>
```

Jinak není třeba nic měnit — plugin JS najde elementy sám podle `data-filter-*` atributů a manipuluje s nimi.

**Vlastní widget vs standardní DOM update:**

Když widget nechce, aby plugin manipuloval s DOM (např. custom combobox s vlastní hide/show logikou), stačí neuvádět `data-facet-count` (žádný text se neaktualizuje) nebo nepoužívat `[data-combobox-option]`/`[data-combobox]` wrappers. Plugin update pak není destruktivní pro custom UI — jen updatuje třídy na `[data-filter-value]` elementu.

Alternativně widget může poslouchat `krizky-filters:update` event a číst `e.detail.facets[dim][slug]` — plný přehled o dostupných počtech. Viz [javascript.md](javascript.md#facets).

## CSS class hooks

| Class | Použití |
|---|---|
| `.pill--active` | JS ji přepíná na `[data-filter-value]` elementech podle aktivního stavu |
| `.is-disabled` | JS ji přepíná na dimenzi kontejneru (`[data-combobox]`) nebo na jednotlivých hodnotách (facet mode `disable`) |
| `[data-facet-hidden]` | JS ho přidává na hodnoty skryté kvůli facetě — combobox JS ho musí respektovat při search (neodemykat) |
| Vše ostatní | Volitelné — projekt si stylizuje, jak chce |

CSS pluginu (`filters.css`) obsahuje jen minimum — základní styly pro `.filter-widget`, `.filter-chip`, `.filter-active` a loading state gridu. Projekt s vlastním designem toto obvykle nepotřebuje.
