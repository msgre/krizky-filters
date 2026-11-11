# Specifikace: js-only-widget

- **Repo:** `krizky-filters`
- **Zdroj:** `krizky/TODO.md` (2026-07-17: „oddělit striktně JS a statiku, vyhledávací políčko bez JS nemůže fungovat“). Rozsah se ujasnil v grillingu 2026-11-11.

## Cíl

Bez JS se nemá zobrazit ovládání filtrů, které bez JS nefunguje. Co bez JS funguje (odkazy na stránky kategorií), zůstane vidět. S JS se ovládání zobrazí hned při prvním vykreslení stránky, bez poskakování layoutu.

Dnes se celý widget vykresluje staticky. Bez JS je vidět textové hledání, které nic nedělá, a volby select a multiselect vedou na `#`, protože šablony čtou neexistující klíč (viz část 1).

## 1. Oprava odkazů ve volbách select a multiselect

`_filter_widget_select.html` a `_filter_widget_multiselect.html` používají `href="{{ _v.fallback_url or '#' }}"`, ale `fetch_filter_values` (`krizky_filters/values.py`) vrací URL v klíči `url`. `fallback_url` proto nikdy neexistuje a každá volba vede na `#`. `docs/configuration.md` (sekce `url`) přitom slibuje, že bez JS klik navede na URL kategorie.

- V obou šablonách použít `_v.url`. Volba bez URL dál vede na `#`.

**Akceptace:**
- Test vykreslí oba widgety pro dimenzi s URL šablonou a ověří, že `href` voleb obsahuje URL kategorie (například `/typ/kriz.html`). Pro dimenzi bez URL ověří `href="#"`.

## 2. Atribut `data-filter-js-only` a třída `filter-js`

Obecný háček: prvek s atributem `data-filter-js-only` se zobrazí jen tehdy, když JS běží a filtrování se podařilo oživit. Atribut může použít jakákoli šablona, i přebitá v projektu.

- `inject_head` vrátí pro stránky s `filters:` kromě odkazu na `filters.css` i inline skript, který nastaví třídu `filter-js` na `<html>`:
  `<script>document.documentElement.classList.add('filter-js')</script>`
  Inline skript v `<head>` se spustí dřív, než prohlížeč vykreslí `<body>`, takže ovládání nenaskakuje. Pro stránky bez `filters:` vrací `inject_head` dál `None`.
- `filters.css` dostane pravidlo `html:not(.filter-js) [data-filter-js-only] { display: none; }`. Atribut `hidden` se pro tento účel nepoužívá.
- `filters.js` odebere třídu `filter-js` z `<html>` pokaždé, když filtrování neoživí. Ovládání se pak skryje a stránka zůstane ve statické podobě. Jde o tyto případy:
  - chybí `#filter-config` nebo nejde naparsovat,
  - na stránce není mřížka (`gridSelector`),
  - selže načtení nebo parsování JSONu (dnešní `.catch`).
- Text, který uživatel napíše do textového hledání před načtením dat, se po načtení použije. Má přednost před hodnotou z URL a promítne se do filtru i do URL.
- Do seznamu háčků v hlavičkovém komentáři `filters.js` přibude `[data-filter-js-only]`.
- Názvy `data-filter-js-only` a `filter-js` jsou stejné v šablonách, CSS i JS (`cross-language.md`).

**Známé omezení (zapsat do dokumentace):** když se inline skript spustí, ale `filters.js` se nenačte (například 404 po chybném nasazení), zůstane ovládání vidět a nebude fungovat.

**Akceptace:**
- Test: `inject_head` pro stránku s `filters:` obsahuje inline skript s `filter-js` i odkaz na CSS. Pro stránku bez `filters:` vrací `None`.
- V diffu `filters.css` je pravidlo pro `html:not(.filter-js) [data-filter-js-only]`.
- V diffu `filters.js` se třída odebírá ve všech třech případech výše a text napsaný před načtením dat se po načtení použije. Kód závislý na DOM se netestuje (`CLAUDE.md`).

## 3. Příznak `_dim.js_only` a výchozí šablona widgetu

- `extra_template_vars` přidá každé dimenzi v `page_filters` klíč `js_only`:
  - `True` pro `type: text`,
  - `True` pro select a multiselect bez URL šablony (`_resolve_url_template` vrátí prázdný řetězec),
  - jinak `False`.
- Výchozí `_filter_widget.html`:
  - přidá `data-filter-js-only` na obal dimenze (`.filter-dimension`), když má `_dim.js_only`,
  - přidá `data-filter-js-only` na obal widgetu (`[data-filter-widget]`), když mají `js_only` všechny dimenze stránky. Klíče začínající `_` (například `_card_template`) nejsou dimenze.
- `_dim.js_only` je součást kontextu šablon, takže ho můžou použít i přebité šablony projektu.
- Vygenerovaný JSON ani konfigurace filtrů pro JS (`#filter-config`) se nemění.

**Akceptace:**
- Test: `page_filters` má `js_only` správně pro textovou dimenzi, pro select nebo multiselect s URL šablonou (explicitní `url` i auto-detekce) a bez ní.
- Test vykreslí `_filter_widget.html`. Textová dimenze a dimenze bez URL mají `data-filter-js-only`, dimenze s URL ne. Obal widgetu má atribut, jen když ho mají všechny dimenze.
- `scripts/verify` projde.

## 4. Dokumentace (docs-sync)

- `docs/widgets.md`:
  - atribut `data-filter-js-only` a třída `filter-js`, jak fungují,
  - `_dim.js_only` v tabulce kontextu,
  - návod, jak atribut použít ve vlastní (přebité) šabloně,
  - známé omezení z části 2.
- `docs/javascript.md`: nový háček a chování, když se filtrování nepodaří oživit.
- `docs/configuration.md`: ověřit, že popis `url` (bez JS klik navede na URL kategorie) po opravě z části 1 sedí.
- `README.md`: aktualizovat, pokud popisuje chování widgetu bez JS.

**Akceptace:**
- Dokumentace popisuje atribut, třídu, `_dim.js_only` i známé omezení.

## Mimo rozsah (rozhodnuto 2026-11-11)

- **Šablony webu `valasske_nebe_ng`:** přebíjí celý widget (panel `fbar`) a swarm v tom repu zatím nepracuje. Atribut se tam doplní později ručně (`krizky/TODO.md`, 2026-11-11).
- **`krizky-map`:** oddělení JS a statiky přijde později (`krizky/TODO.md`, 2026-11-11).
- **Generování widgetu v JS:** zamítnuto, přestalo by fungovat přebíjení šablon.
- **Čekání na data před zobrazením ovládání:** zamítnuto, ovládání se má ukázat hned při vykreslení.

## Poznámky pro plánovače

- Části 1 až 3 mění šablony v `krizky_filters/templates/` a `tests/test_filter_plugin.py`. Části 2 a 3 navíc sdílí `krizky_filters/plugin.py`. Rozpad na tikety nech na sobě, ale počítej s tím, že by tikety nad stejnými soubory běžely za sebou.
- Testy, které vykreslují šablony pluginu přes Jinja2, dnes neexistují. Loader šablon nastavuje `prepare_jinja2_environment` v `plugin.py`.
