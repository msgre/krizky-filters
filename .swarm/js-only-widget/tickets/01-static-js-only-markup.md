---
id: "01"
slug: static-js-only-markup
title: Statická strana widgetu – opravené odkazy, js_only, třída filter-js a CSS pravidlo
status: pending
depends_on: []
files:
  - krizky_filters/plugin.py
  - krizky_filters/templates/_filter_widget.html
  - krizky_filters/templates/_filter_widget_select.html
  - krizky_filters/templates/_filter_widget_multiselect.html
  - krizky_filters/assets/krizky-filters/filters.css
  - tests/test_filter_plugin.py
  - docs/widgets.md
  - docs/configuration.md
  - README.md
attempts: 0
pr: ""
---

## Cíl
Bez JS se nemá zobrazit ovládání filtrů, které bez JS nefunguje, a odkazy na kategorie mají bez JS opravdu vést na stránky kategorií. Tiket pokrývá celou Python, šablonovou a CSS stranu specifikace `.swarm/js-only-widget/spec.md`: část 1 (oprava `href` ve volbách), z části 2 `inject_head` s inline skriptem a pravidlo ve `filters.css`, celou část 3 (`_dim.js_only` a atribut `data-filter-js-only` ve výchozí šabloně) a dokumentaci k tomu (část 4 kromě `docs/javascript.md`). Chování `filters.js` řeší tiket 02.

## Akceptační kritéria
- `_filter_widget_select.html` a `_filter_widget_multiselect.html` používají `href="{{ _v.url or '#' }}"`. `git grep -n fallback_url -- ':!.swarm'` nic nenajde.
- `inject_head` vrací pro stránku s `filters:` odkaz na `/krizky-filters/filters.css` a navíc `<script>document.documentElement.classList.add('filter-js')</script>`. Pro stránku bez `filters:` vrací dál `None`.
- `filters.css` obsahuje pravidlo `html:not(.filter-js) [data-filter-js-only] { display: none; }`. Atribut `hidden` se k tomu nepoužívá.
- `extra_template_vars` přidá každé dimenzi v `page_filters[page]` klíč `js_only`: `True` pro `type: text`, `True` pro select/multiselect, když `_resolve_url_template` vrátí prázdný řetězec, jinak `False`. Klíč `_card_template` se nemění a `js_only` nedostane.
- Výchozí `_filter_widget.html` dá atribut `data-filter-js-only` na `.filter-dimension`, když má `_dim.js_only`. Na obal `[data-filter-widget]` ho dá, jen když mají `js_only` všechny dimenze stránky (klíče začínající `_` se nepočítají).
- `_build_filter_config` (obsah `#filter-config`) ani vygenerovaný JSON se nemění. Stávající testy `test_build_filter_config_*` a `test_generate_filter_json_*` projdou beze změny.
- Dokumentace:
  - `docs/widgets.md` popisuje atribut `data-filter-js-only` a třídu `filter-js` (kdo třídu nastavuje a že ji `filters.js` odebere, když filtrování neoživí, s odkazem na `docs/javascript.md`). V tabulce kontextu přibude `_dim.js_only` a v tabulce chybí jen `select | multiselect`, doplň i `text`. Je tam krátký návod, jak atribut použít v přebité šabloně, a známé omezení: když se inline skript spustí, ale `filters.js` se nenačte (např. 404), ovládání zůstane vidět a nebude fungovat.
  - `docs/configuration.md`: popis `url` (bez JS klik navede na URL kategorie) sedí. Uprav ho, pokud nesedí.
  - `README.md`: odstavec o chování bez JS (řádek 5) zmíní, že ovládání fungující jen s JS (textové hledání, volby bez URL kategorie) se bez JS nezobrazí.
- `scripts/verify` skončí s exit 0.

## Testy
Nejdřív napiš selhávající testy v `tests/test_filter_plugin.py`, pak implementuj.
1. Úprava `test_inject_head_with_filters`: výsledek obsahuje `filter-js`, `<script>` i `filters.css`. `test_inject_head_without_filters` zůstane (`None`).
2. Test `js_only` v `page_filters` přes `FiltersPlugin().extra_template_vars(...)` (vzor: `test_extra_template_vars_text_dim`, fixture `conn`): textová dimenze → `True`; select i multiselect s explicitním `url` → `False`; s URL auto-detekovanou z category stránky (`category: <dim>` se stejným `many`) → `False`; bez URL → `True`.
3. Test vykreslení šablon přes Jinja2 (dnes žádný neexistuje). Stačí `jinja2.Environment(loader=FileSystemLoader(<krizky_filters/templates>))` a ručně sestavený kontext `page_name` + `page_filters` (nebo výstup `extra_template_vars`):
   - `_filter_widget_select.html` i `_filter_widget_multiselect.html` (přes `_filter_widget.html` nebo přímo s `_dim_key`/`_dim`) pro dimenzi s URL šablonou: `href` voleb obsahuje URL kategorie, např. `/typ/kriz.html`. Pro dimenzi bez URL `href="#"`.
   - `_filter_widget.html`: textová dimenze a dimenze bez URL mají na `.filter-dimension` `data-filter-js-only`, dimenze s URL ne. Obal `data-filter-widget` má atribut, jen když ho mají všechny dimenze (otestuj obě varianty: smíšené dimenze a jen js_only dimenze).
   Atributy ověřuj parsováním nebo dostatečně přesným regexem na konkrétní element, ne jen `"data-filter-js-only" in html`.

## Poznámky
- Guidelines: `/Users/msgre/projects/muzeum/krizky/docs/guidelines/python.md` (bez `from __future__ import annotations`), `cross-language.md` (názvy `data-filter-js-only` a `filter-js` přesně stejně v šablonách, CSS i JS, tiket 02 je používá ve `filters.js`), `docs-sync.md`, `security.md`.
- `js_only` počítej v `extra_template_vars` u každé dimenze. Pro select/multiselect už se tam `url_template` počítá, tak ho použij. U neznámého typu dimenze platí „jinak `False`“ podle URL logiky. Nevymýšlej pro něj zvláštní pravidlo.
- Pro „všechny dimenze jsou js_only“ v šabloně stačí Jinja2 výraz nad `_dims.items()` s vynecháním klíčů začínajících `_`. Pozor: stránka bez dimenzí nemá skončit s atributem na obalu kvůli prázdnému `all()`. Prázdný widget stejně nic neovládá, takže obě volby jsou přijatelné, ale rozhodnutí popiš v komentáři šablony.
- `prettier --check` kontroluje i `filters.css`, po úpravě spusť `npx --no-install prettier --write 'krizky_filters/assets/**/*.{js,css}'`.
- `filters.js` neměň, patří tiketu 02. Taky neměň `docs/javascript.md`.
- Šablony webu `valasske_nebe_ng` a plugin `krizky-map` jsou mimo rozsah.

## Otázky
