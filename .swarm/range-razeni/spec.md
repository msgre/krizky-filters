# Specifikace: range-razeni

- **Repo:** `krizky-filters`
- **Zdroj:** rozhovor o webu pro projekt `sreality` (`/Users/msgre/projects/domov/sreality`, grilling 2026-11-24, otázky Q1, Q15, Q23, Q31 a Q32). Web s inzeráty bytů potřebuje filtrovat podle ceny, plochy a ceny za m² a řadit výpis podle těchto hodnot. Uživatel chce, aby z toho vzniklo obecné rozšíření pluginu použitelné i jinde (třeba datace ve Valašském nebi). Body označené *(upřesněno ve specifikaci)* doplnil autor specifikace.

## Cíl

1. Nový typ dimenze **`range`**: číselný rozsah od–do nad jedním polem záznamu. Funguje jen s JS a chová se k ostatním dimenzím stejně jako ony k sobě navzájem (AND mezi dimenzemi a fasety podle ostatních dimenzí).
2. **Řazení záznamů** ve výsledcích: volitelný select „Řadit podle“ nad poli nastavenými v configu stránky, se stavem v URL.

Stávající chování dimenzí `select`, `multiselect` a `text`, JSON filtru a stránek bez nových klíčů se nemění.

## 1. Dimenze `type: range`

### Konfigurace

```yaml
filters:
  dimensions:
    cena:
      label: Cena
      type: range
      unit: Kč          # volitelné: text za polem (a v chipu aktivního filtru)
      step: 100000      # volitelné: atribut step číselného pole, výchozí "any"
```

- Klíč dimenze je zároveň **název pole záznamu** a **název parametru v URL**, stejně jako u ostatních typů. Nepotřebuje sloupec `<dim>_slug`.
- `many`, `sort` a `search_fields` se u `range` nepoužijí. Když jsou uvedené, plugin zaloguje varování.
- Neplatné `step` (ne kladné číslo) nebo `unit` (ne řetězec) → varování a výchozí hodnota.

### Python

- `_DIM_TYPES` dostane `range`. Text varování o neznámém typu vyjmenuje i `range`.
- `extra_template_vars`: dimenze `range` má v `page_filters` položky `label`, `type: "range"`, `values: []`, `js_only: True`, `unit` a `step`. Min a max se v Pythonu **nepočítají**: widget je jen s JS a JS je počítá z načteného JSON *(upřesněno ve specifikaci; statické hodnoty by počítaly i se záznamy mimo stránku, viz `fetch_filter_values`)*.
- `_build_filter_config`: dimenze `range` dostane `{label, type: "range", unit, step}`.
- Výchozí šablona `_filter_widget_range.html` (vybírá ji `_filter_widget.html` podle typu):
  - dvě pole `<input type="number" inputmode="decimal" min="0">` s atributy `data-filter-range="min"` a `data-filter-range="max"` a `data-filter-dimension="<dim>"`,
  - popisky „od“ a „do“, `unit` za poli a `step` z configu.
  - Šablonu jde přebít v projektu jako ostatní.
- Obal dimenze má díky `js_only` atribut `data-filter-js-only` (stávající mechanismus).

### JS (`filters.js`)

- **Stav:** aktivní rozsah je v `state` uložený jako **jeden řetězec** v `Set`, stejně jako textová dimenze. Tvar `activeState` v události `krizky-filters:update` se tím nemění.
- **URL:** `?cena=3000000-5000000`, jen dolní mez `?cena=3000000-`, jen horní mez `?cena=-5000000`.
  - Čísla jsou nezáporná, desetinná s tečkou (`52.5`).
  - Neplatná hodnota (`abc`, `1-2-3`, `-`, prázdné obě meze) se ignoruje, jako by parametr nebyl.
  - Když je min > max, meze se prohodí *(upřesněno ve specifikaci)*.
  - Serializace vrací kanonický tvar (`3000000-5000000`, bez nadbytečných nul a mezer).
- **Shoda:** meze jsou včetně. Záznam, jehož hodnota pole je `null`, chybí nebo není číslo, při aktivním rozsahu **neprojde**. Bez aktivního rozsahu projde každý záznam. Číselný řetězec (`"52.5"`) se bere jako číslo *(upřesněno ve specifikaci)*.
- **Ovládání:**
  - Změna pole (`change` a `input` s debounce 300 ms) aktualizuje stav, URL i výsledky a vrátí stránkování na stranu 1.
  - Prázdné obě meze = dimenze není aktivní.
  - Při načtení stránky se pole vyplní z URL. Back/forward funguje jako u ostatních dimenzí.
- **Fasety** (rozhodnutí Q31: stejné chování jako ostatní dimenze):
  - Placeholdery polí jsou min a max pole přes záznamy, které projdou všemi aktivními filtry **kromě** tohoto rozsahu (`matchesAllExcept`). Bez fasetů se počítají přes všechny záznamy.
  - Když takový záznam není, placeholdery jsou prázdné.
  - Aktivní rozsah zužuje fasety ostatních dimenzí, protože se účastní `matchesAllExcept` jako každá jiná dimenze.
  - Rozsah sám počty hodnot nemá a `computeFacets` ho přeskočí jako textovou dimenzi.
- **Aktivní filtry:**
  - Chip v `[data-filter-active-list]` má tvar „Cena: 3 000 000–5 000 000 Kč“, „Cena: od 3 000 000 Kč“ nebo „Cena: do 5 000 000 Kč“. Čísla se formátují `toLocaleString(document.documentElement.lang || undefined)`.
  - Odebrání chipu vyprázdní obě pole.
  - `[data-filter-clear]` vyprázdní i rozsahy.
- Nové hook atributy `[data-filter-range]` se přidají do hlavičkového komentáře `filters.js`.

**Akceptace:**
- Python testy:
  - `page_filters` a `_build_filter_config` pro dimenzi `range` (s `unit` a `step` i bez nich),
  - varování pro `range` s `many`, `sort` nebo `search_fields` a pro neplatné `step`,
  - vykreslení `_filter_widget.html` s dimenzí `range`: dvě pole s `data-filter-range` a `data-filter-js-only` na obalu dimenze,
  - stránka se `select` i `range` dimenzí: obal widgetu nemá `data-filter-js-only` (select s URL).
- JS testy čistých funkcí (`node --test`, `tests/js/*.test.mjs`):
  - parsování a serializace hodnoty rozsahu (`parametrize`-styl tabulka: platné tvary, prohozené meze, desetinné číslo, neplatné tvary),
  - shoda záznamu s rozsahem (meze včetně, `null`, chybějící pole, číselný řetězec, jen dolní a jen horní mez),
  - výpočet min a max pole přes seznam záznamů (ignoruje `null` a nečíselné hodnoty, prázdný seznam).

## 2. Řazení záznamů

### Konfigurace

```yaml
filters:
  sort_records:
    param: sort              # volitelné, název parametru v URL, výchozí "sort"
    default_label: Nejnovější  # volitelné, popisek výchozího řazení, výchozí "Výchozí řazení"
    options:
      - {field: cena, label: Cena}
      - {field: plocha, label: Plocha}
      - {field: cena_m2, label: Cena za m²}
```

- **Výchozí řazení** je pořadí záznamů v JSON filtru, tedy pořadí stránky z buildu (`order_by` stránky v krizky). JS ho při volbě výchozího řazení **nemění**. Výchozí řazení tak je stejné s JS i bez něj *(upřesněno ve specifikaci; odpadá klíč `default`, který by se mohl rozejít s `order_by` stránky)*.
- **Volby v selectu:** výchozí řazení a pro každou položku `options` dvě varianty, vzestupně a sestupně. Výchozí popisky jsou „{label} ↑“ a „{label} ↓“. Texty jsou v přebitelné šabloně.
- **URL:** `?sort=cena` (vzestupně), `?sort=-cena` (sestupně). Hodnota mimo `options` se ignoruje. Výchozí řazení parametr v URL nemá.
- **Varování** (log při buildu, build pokračuje):
  - `param` koliduje s klíčem dimenze,
  - `options` chybí nebo je prázdné,
  - položka nemá `field` nebo `label`,
  - `filters.fields` je nastavené a neobsahuje `field` některé položky (v JSON by pole chybělo).

### Python

- `extra_template_vars`: `page_filters[page]["_sort_records"]` = `{param, default_label, options}`, jen když je `sort_records` nastavené. Klíč začíná `_`, takže ho šablona a kód nepovažují za dimenzi (stejně jako `_card_template`).
- `_build_filter_config`: `sortRecords: {param, options: [{field, label}]}`, nebo `null` bez configu. Názvy klíčů podle `cross-language.md`.
- Nová šablona `_filter_sort.html`:
  - `<select data-filter-sort>` s volbami podle konfigurace,
  - obal s `data-filter-js-only`,
  - `_filter_widget.html` ji vloží, když `_sort_records` existuje.
  - Projekt ji může přebít nebo umístit jinam vlastním `{% include %}`.

### JS

- **Postup:** řazení se aplikuje na vyfiltrované záznamy **před stránkováním**. Výsledek se vykreslí kartami a změna řazení vrátí stránkování na stranu 1.
- **Porovnání:**
  - Řazení je stabilní, při shodě zůstává výchozí pořadí.
  - Hodnoty `null`, chybějící a prázdný řetězec jdou **vždy na konec**, bez ohledu na směr.
  - Čísla a číselné řetězce se porovnávají číselně, ostatní řetězce přes stávající `sortKeyAlpha` (bez diakritiky a velikosti písmen).
- Stav řazení se čte z URL při načtení a při back/forward a zapisuje se do URL spolu s filtry (`serializeState`).
- Událost `krizky-filters:update` má v `detail` nový klíč `sort` (`"-cena"`, `"cena"` nebo `null`). `filteredRecords` jsou v pořadí po seřazení.
- `[data-filter-clear]` řazení **neresetuje**, není to filtr *(upřesněno ve specifikaci)*.

**Akceptace:**
- Python testy:
  - `page_filters["_sort_records"]` a `sortRecords` v `_build_filter_config` (s výchozím `param` a `default_label` i bez nich),
  - bez `sort_records` klíče chybí nebo jsou `null`,
  - každé varování z části 2 (`parametrize`),
  - vykreslení `_filter_widget.html`: select má výchozí volbu a 2 volby na položku a obal má `data-filter-js-only`.
- JS testy čistých funkcí:
  - parsování hodnoty řazení z URL (platná, sestupná, neznámé pole, prázdná),
  - porovnávací funkce a řazení seznamu záznamů: čísla, číselné řetězce, text s diakritikou, `null` na konci v obou směrech, stabilita při shodě.

## 3. Testovatelnost JS

`CLAUDE.md` povoluje testovat jen čisté funkce přes `node --test` a zakazuje přepisovat stávající kód kvůli testům. Nové čisté funkce (parsování a serializace rozsahu, shoda s rozsahem, min a max, parsování řazení, porovnání a řazení záznamů) proto musí být dostupné testům bez DOM. Jak je zpřístupnit, rozhodne plánovač. Musí přitom platit:

- v prohlížeči se dál načítá jediný `filters.js` (`inject_body_end` se nemění), nebo se přidá druhý soubor přes stejný hook a obě cesty jsou v dokumentaci,
- stávající funkce se kvůli testům nepřesouvají ani nepřepisují,
- ESLint a Prettier procházejí bez změny jejich konfigurace.

`tests/js/` zatím neexistuje. `scripts/verify` ho spouští, když v něm jsou soubory `*.test.mjs`.

## 4. Dokumentace (docs-sync)

- **`docs/configuration.md`:**
  - typ `range` (klíče, URL formát, chování s `null`, fasety, omezení na nezáporná čísla),
  - sekce `sort_records` (klíče, URL, výchozí řazení = `order_by` stránky, `null` na konci),
  - nová varování v seznamu validací.
- **`docs/widgets.md`:** šablony `_filter_widget_range.html` a `_filter_sort.html`, jejich hook atributy a přebití.
- **`docs/javascript.md`:**
  - range ve stavu a URL,
  - fasety pro range (placeholdery),
  - klíč `sort` v `krizky-filters:update`,
  - pořadí `filteredRecords`.
- **`README.md`:** do „Klíčové vlastnosti“ přibude rozsahový filtr a řazení výsledků a minimální ukázka configu.

**Akceptace:** dokumentace popisuje všechny nové klíče, atributy, formáty URL a varování.

## Mimo rozsah

- Dvojitý posuvník u rozsahu (rozhodnutí Q15: jen dvě číselná pole, posuvník případně později).
- Statické stránky nebo fallback bez JS pro rozsah a řazení.
- Záporná čísla a data (datum) v rozsahu.
- Filtry na stránkách kategorií (zapsáno v `krizky/TODO.md` jako námět z téhož rozhovoru).
- Zapojení do webu `sreality` proběhne v tamním repu samostatným krokem po sloučení tohoto běhu.
- Úpravy core `krizky` a ostatních pluginů.

## Poznámky pro plánovače

- Doporučené pořadí:
  1. Zpřístupnění nových čistých funkcí testům (část 3) a jejich testy pro range i řazení.
  2. `range` v Pythonu a šablona widgetu.
  3. `range` v JS (stav, URL, shoda, fasety a placeholdery, chipy).
  4. `sort_records` v Pythonu a šablona selectu.
  5. Řazení v JS.
  6. Dokumentace.

  Tikety 2 a 4 můžou běžet souběžně. Tikety 3 a 5 mění stejný `filters.js`, proto by měly jít po sobě.
- Guidelines jsou v `/Users/msgre/projects/muzeum/krizky/docs/guidelines/` (`python.md`, `javascript.md`, `cross-language.md`, `docs-sync.md`, `security.md`). Hodnoty z URL se do DOM vkládají jen přes `textContent` a atributy, nikdy jako HTML.
- Kód závislý na DOM se netestuje (`CLAUDE.md`). Chování v prohlížeči ověří uživatel na webu `sreality` po zapojení.
