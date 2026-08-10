# krizky-filters

Plugin pro [krizky](https://github.com/…/krizky) přidávající multidimenzionální filtrování záznamů v prohlížeči přes **progressive enhancement**.

Bez JavaScriptu zůstává web plně funkční — pill-tlačítka jsou obyčejné `<a href>` odkazy na statické category stránky. S JavaScriptem se navigace intercepuje, filtry se aplikují in-browser nad odlehčeným JSON souborem, výsledky se překreslují klonováním `<template>` tagu a stav filtrů se ukládá do URL.

## Klíčové vlastnosti

- **AND mezi dimenzemi, OR uvnitř dimenze** — kombinace více dimenzí (typ AND datace AND štítek) a více hodnot v rámci dimenze (baroko OR hřbitov)
- **Facety** (volitelné) — dynamicky přepočítávané počty a skrývání/graying nedostupných hodnot podle aktuálního výběru
- **Konfigurovatelné řazení** — `count` (populární nahoře), `alpha` (abecedně) nebo multi-column syntax (`-count,alpha`)
- **URL state** — číslo stránky v cestě (`/mista-2.html`), filtry v query params (`?typ=kriz&stitky=baroko`), funguje back/forward, bookmarking, sdílení odkazů
- **JS stránkování** — vlastní stránkování nad filtrovanými výsledky, stejná logika jako Python paginátor (window + boundary + ellipsis)
- **Custom event** — `krizky-filters:update` po každé změně filtrů umožní připojit vlastní UI (comboboxy, counter, chip lišta)
- **Přetěžování šablon** — všechny výchozí widgety jsou v samostatných Jinja2 souborech, projekt je jednoduše přebije umístěním souboru se stejným jménem do vlastního `templates/`

## Instalace

```bash
pip install krizky-filters
```

Pro lokální vývoj (editable install):

```bash
pip install -e /cesta/k/_plugins/krizky-filters
```

Plugin se aktivuje automaticky přes entry point `krizky` (viz `pyproject.toml`).

## Minimální konfigurace

Do `config.yaml` přidej klíč `filters:` k stránce, na které chceš filtrování aktivovat:

```yaml
site:
  pages:
    vsechna_mista:
      template: vsechna_mista.html
      path: /vsechna-mista.html
      filters:
        fields: [slug, nazev, typ, typ_slug, stitky, stitky_slug]
        card_template: _karta_filter.html
        dimensions:
          typ:
            label: Typ
            type: select
          stitky:
            label: Štítek
            type: multiselect
            many: true
```

Detailní reference: [docs/configuration.md](docs/configuration.md)

## Nutné úpravy šablon

Aby se plugin propojil s projektem, potřebuje 3 hooky v šablonách:

**1. Base layout** — přidej dvě místa pro inject:
```html
<head>
  ...
  {{ head_injections | safe }}   {# CSS pluginu #}
</head>
<body>
  ...
  {{ body_end_injections | safe }}  {# JS + filter config pluginu #}
</body>
```

**2. Stránka s filtry** — vlož widget a card template:
```jinja2
{% include "_filter_widget.html" %}

<div class="grid" data-filter-grid>
  {% for record in filtered %}
    {% include "_karta.html" %}
  {% endfor %}
</div>

{% include "_filter_card_template.html" %}
```

**3. Card partial pro JS klonování** (`_karta_filter.html`) — obsahuje `data-field` atributy:
```jinja2
<a class="card" href="/{{ record.slug }}.html" data-field="slug" data-href-pattern="/{value}.html">
  <img data-field-photo="id_radku" data-photo-size="thumb" data-photo-format="jpg" src="">
  <h3 data-field="nazev">{{ record.nazev }}</h3>
  ...
</a>
```

Podrobnosti k card partialu: [docs/card-template.md](docs/card-template.md)

## Dokumentace

- **[docs/configuration.md](docs/configuration.md)** — kompletní reference konfigurace v `config.yaml`
- **[docs/widgets.md](docs/widgets.md)** — jak funguje výchozí widget, jak přebít existující, jak přidat nový typ (combobox, slider, boolean)
- **[docs/card-template.md](docs/card-template.md)** — jak funguje `data-field`, `data-field-photo`, `data-truncate`, `data-date-format`, `data-href-pattern`
- **[docs/javascript.md](docs/javascript.md)** — JS API: events, data-attribute hooks, URL state, custom UI (chip lišta, počítadlo, clear tlačítka)

## Architektura ve zkratce

Plugin implementuje pluggy hooky:

| Hook | Co dělá |
|---|---|
| `prepare_jinja2_environment` | Přidá plugin templates do Jinja2 loaderu (za project, před built-in) |
| `extra_template_vars` | Spočítá `page_filters` dict s hodnotami a metadaty všech dimenzí |
| `inject_head` | CSS link tag do `<head>` |
| `inject_body_end` | Filter config JSON + JS script tag před `</body>` |
| `after_page_written` | Vygeneruje filter JSON, zkopíruje JS/CSS assets do output |

Runtime flow v prohlížeči:

```
1. Načti #filter-config JSON z HTML
2. Fetch filter JSON (odlehčený, obsahuje jen fields uvedené v filters.fields)
3. Parsuj URL → obnov stav filtrů a číslo stránky
4. Připni listenery na [data-filter-value] elementy
5. Při změně: aplikuj filtr → překresli grid klonováním <template id="card-template"> → aktualizuj URL → dispatch krizky-filters:update event
```

## Licence

MIT
