# Card template

Karta jednoho záznamu v JS-filtrovaném gridu se vyrábí přes native `<template>` element, který JS klonuje pro každý filtrovaný záznam a plní přes `data-*` atributy.

## Základní princip

Jinja2 partial (např. `_karta_filter.html`) se **jednou při buildu** vyrenderuje s prvním záznamem (`filtered[0]`) a zabalí do `<template id="card-template">`. Obsah `<template>` prohlížeč sám nerenderuje — slouží pouze jako předloha pro JS.

Při každé změně filtru JS:

1. Vezme filtrované záznamy
2. Pro každý naklonuje obsah `<template>`
3. Projde všechny `data-field*` elementy a dosadí hodnoty z JSON dat záznamu
4. Vloží klony do gridu

**Design goal:** karta je definována na jednom místě (Jinja2 partial). SSR loop používá plný `picture()` macro pro maximální kvalitu obrázků, JS varianta používá lightweight `<img>` s dynamicky sestavovaným src. To vyžaduje dvě odděleně šablony — plné `_karta.html` pro SSR a lightweight `_karta_filter.html` pro JS.

## `data-field`

Nejjednodušší varianta — dosadí hodnotu záznamu jako textový obsah.

```html
<h3 data-field="nazev">Ukázka</h3>
<span class="place" data-field="umisteni">Ukázka</span>
```

JS:
- Přečte `record[data-field]`
- Nastaví `el.textContent = value`

Pro `<img>` a `<a>` elementy má speciální chování:

### `<img data-field="X">` — nastaví `src`

```html
<img data-field="thumbnail_url" src="" alt="">
```

JS: `el.src = record.thumbnail_url`.

Pokud používáš auto-sestavení URL fotky z ID záznamu (doporučené), použij radši `data-field-photo` — viz níže.

### `<a data-field="X">` — nastaví `href`

```html
<a data-field="url">
```

JS: `el.href = record.url`.

S `data-href-pattern` (viz níže) můžeš mít URL sestavenou ze slug pole + pattern.

## `data-href-pattern`

Sestaví `href` z hodnoty pole + URL pattern. Užitečné, když v datech máš jen slug a URL je konstantní vzor:

```html
<a data-field="slug" data-href-pattern="/{value}.html" href="">
```

JS: `el.href = "/{slug}.html".replace("{value}", record.slug)` → `/kriz-u-muzika.html`

Placeholder `{value}` se nahrazuje hodnotou pole z `data-field`.

## `data-field-item-class` — pole hodnot (tagy)

Když hodnota v JSONu je pole (např. `stitky: ["baroko", "hrbitov"]`), potřebuješ pro každý prvek vygenerovat samostatný element:

```html
<div class="card-tags"
     data-field="stitky"
     data-field-item-class="tag tag--plain">
  {# SSR renderuje spans normálně přes {% for %} #}
  {% for t in record.stitky %}<span class="tag tag--plain">{{ t }}</span>{% endfor %}
</div>
```

JS vygeneruje:
```html
<div class="card-tags">
  <span class="tag tag--plain">baroko</span>
  <span class="tag tag--plain">hrbitov</span>
</div>
```

Když je pole prázdné nebo `null`, JS element skryje (`hidden` atribut).

## `data-field-photo` — URL fotky

Sestaví URL fotky z ID záznamu, velikosti a formátu — používá `sources.photos.base_url` z krizky configu:

```html
<img src=""
     data-field-photo="id_radku"
     data-photo-size="thumb"
     data-photo-format="jpg"
     data-photo-pad="3"
     alt="{{ record.nazev }}"
     loading="lazy">
```

| Atribut | Default | Popis |
|---|---|---|
| `data-field-photo` | — | Název pole v JSONu, které obsahuje ID řádku |
| `data-photo-size` | `thumb` | Název varianty z `sources.photos.sizes` |
| `data-photo-format` | `jpg` | Přípona souboru |
| `data-photo-pad` | `3` | Zero-padding délky ID (jak dělá Python `f"{id:03d}"`) |

JS:
- Vezme `record[data-field-photo]`, zero-paduje na `data-photo-pad` míst
- Sestaví URL: `{photosBaseUrl}/{padded_id}_{size}.{format}` (např. `https://cdn.example.com/007_thumb.jpg`)
- Nastaví `el.src` a připne `onload` (odebere `.placeholder` z parent `[data-thumb]`) a `onerror` (schová `<img>`)
- Když ID chybí nebo `photosBaseUrl` není nastaven, element skryje

Pattern pro placeholder chování:

```html
<div class="thumb placeholder" data-thumb>
  <img data-field-photo="id_radku" data-photo-size="thumb" data-photo-format="jpg" src="" alt="">
</div>
```

CSS:
```css
.thumb.placeholder { background: repeating-linear-gradient(...); }
```

Když se fotka načte úspěšně, JS odstraní `.placeholder` třídu z `[data-thumb]` a placeholder pattern zmizí. Když foto neexistuje, `onerror` schová `<img>` a placeholder zůstane viditelný.

## `data-truncate` — ořezání textu

Ekvivalent Jinja2 filtru `truncate()`:

```html
<p data-field="pribeh" data-truncate="96">{{ record.pribeh | truncate(96) }}</p>
```

Atributy:

| Atribut | Default | Popis |
|---|---|---|
| `data-truncate` | — | Maximální délka (znaky) |
| `data-truncate-end` | `...` | Suffix při ořezu |
| `data-truncate-leeway` | `5` | Tolerance — pokud text překračuje délku o méně než leeway znaků, neořezává se |
| `data-truncate-killwords` | (bool) | Přítomnost atributu = ořezává i uprostřed slova, jinak na hranici slova |

JS implementuje **přesně stejnou logiku** jako Python Jinja2 `do_truncate` — stejné defaults, stejné chování s leeway a hranicí slova. Výsledek pro stejný vstup je identický.

## `data-date-format` — formátování data

Ekvivalent Jinja2 filtru `strftime`:

```html
<span class="date"
      data-field="vytvoreno"
      data-date-format="{{ site.date_format }}">
  {{ record.vytvoreno | strftime(site.date_format) }}
</span>
```

JS podporuje běžné strftime patterny:

| Pattern | Význam |
|---|---|
| `%-d` | Den bez zero-paddingu |
| `%d` | Den s zero-paddingem (`01`, `02`, ...) |
| `%-m` | Měsíc bez zero-paddingu |
| `%m` | Měsíc s zero-paddingem |
| `%Y` | Rok 4 čísla (`2026`) |
| `%y` | Rok 2 čísla (`26`) |

Datum musí být v JSONu jako ISO string (např. `"2026-08-15"` nebo `"2026-08-15 12:00:00"`). Když parsování selže, JS text nezmění.

## Kompletní příklad `_karta_filter.html`

```jinja2
{% from "_macros.html" import free_tag %}
<a class="card"
   href="/{{ record.slug }}.html"
   data-field="slug"
   data-href-pattern="/{value}.html">

  <div class="thumb placeholder" data-thumb>
    <img src=""
         data-field-photo="id_radku"
         data-photo-size="thumb"
         data-photo-format="jpg"
         alt="{{ record.nazev }}"
         loading="lazy">
  </div>

  <div class="card-body">
    <span class="place" data-field="umisteni">{{ record.umisteni }}</span>
    <h3 data-field="nazev">{{ record.nazev }}</h3>
    <p class="excerpt"
       data-field="pribeh"
       data-truncate="96">{{ record.pribeh | default('') | truncate(96) }}</p>
    <div class="card-tags"
         data-field="stitky"
         data-field-item-class="tag tag--plain">
      {% for t in record.stitky | default([]) %}{{ free_tag(t) }}{% endfor %}
    </div>
    <div class="card-foot">
      <span class="date"
            data-field="vytvoreno"
            data-date-format="{{ site.date_format }}">
        {{ record.vytvoreno | strftime(site.date_format) if record.vytvoreno else '' }}
      </span>
    </div>
  </div>
</a>
```

## SSR vs JS varianta karty — proč dvě šablony?

**SSR karta** (v `{% for record in filtered %}` loopu) používá:
- Plný `picture()` macro s AVIF/WebP/JPEG variantami a srcset
- Ostrý loading (`loading="lazy"` až od druhé viditelné, nastavuje browser)
- Přesná fotografie pro každý záznam

**JS karta** (v `<template id="card-template">`):
- Prostý `<img src="…thumb.jpg">` — JS klonuje a přehrává jen `src`, ne celý `<picture>` strom
- Menší HTML overhead
- Fallback při chybějícím obrázku (onerror)

Proto se doporučuje mít dva partialy:

- `_karta.html` — používá se v SSR loopu (`{% include "_karta.html" %}`)
- `_karta_filter.html` — používá se jako `card_template` v configu

Pokud ti stačí jedna varianta (bez responsivních obrázků), použij jednu šablonu na obou místech.

## Kondicionální rendering v šabloně

Pozor na Jinja2 `{% if %}` guardy — element, který v `<template>` chybí (protože `filtered[0]` má chybějící pole), JS nemůže naplnit u ostatních záznamů. Doporučené workarounds:

- **Nepoužívat guard** — vždy vykresli element, i prázdný. JS ho pak buď naplní, nebo pro pole s `data-field-item-class` skryje.
- **Použít `default()` filtr** — `{{ record.pribeh | default('') | truncate(96) }}` — pole je vždy renderované s prázdným stringem, atributy `data-field` a `data-truncate` na něm jsou vždy dostupné.
- **Podmíněně řešit v CSS** — `.excerpt:empty { display: none; }`.

## Vlastní data-field handlery

Pokud chceš nový typ transformace (např. formátování měny, čísel, custom logic), musíš vidět filters.js. Aktuálně jsou handlery hardkódované — customizace vyžaduje forking / patch. Pokud to bude potřeba, otevřeme mechanismus přes plugin JS API.
