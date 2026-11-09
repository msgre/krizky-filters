# Specifikace: naming-logger

- **Repo:** `krizky-filters`
- **Zdroj:** review konzistence `krizky/reports/2026-08-17-2013/plugin-krizky-filters.md`, nálezy `[recommended]`. Rozsah se rozhodl 2026-11-09 (otázky Q26–Q29 v `~/projects/ai/swarm`).

## Cíl

Dotáhnout dva zbývající nálezy z reviewu, které jdou udělat jen v tomhle repu. Zároveň je to první ostrý běh swarmu, takže rozsah je záměrně malý.

## 1. Přejmenování `FilterPlugin` na `FiltersPlugin`

Jméno třídy má odpovídat balíčku (`krizky_filters`) stejně jako u ostatních pluginů (`MapPlugin`/`krizky_map`, `SharePlugin`/`krizky_share`).

- Přejmenovat třídu v `krizky_filters/plugin.py` včetně instance `plugin = FiltersPlugin()` a všech odkazů v testech a dokumentaci tohoto repa.
- Alias `FilterPlugin` nezůstane. Třída je interní a entry point v `pyproject.toml` odkazuje na instanci `plugin`, ten se nemění.

**Akceptace:**
- `git grep -n FilterPlugin` v repu nic nenajde.
- `scripts/verify` projde.

## 2. Logger a varování při chybné konfiguraci filtrů

Dnes se chybná konfigurace projeví potichu: filtr nefunguje a v logu nic není.

- V `krizky_filters/plugin.py` přidat modulový `_log = logging.getLogger(__name__)`. Konvence jsou v `guidelines/python.md`: jméno `_log`, formátování přes `%s`, ne f-string.
- `_log.warning` se vypíše v těchto případech:
  1. Dimenze má neznámý `type`. Povolené jsou `select`, `multiselect` a `text`, výchozí je `multiselect`.
  2. Dimenze má `type: text` a chybí jí `search_fields`, nebo je seznam prázdný. Hledání by pak nic nenašlo.
  3. `sort` obsahuje neznámý preset nebo sloupec. Platné tvary popisuje `docs/configuration.md` v části Sortování.
  4. `facets_mode` je jiný než `hide` nebo `disable`.
  5. Stránka má `filters:`, ale žádnou dimenzi.
- Zpráva obsahuje název stránky a klíč dimenze, aby šla chyba dohledat. Je anglicky, ve stejném stylu jako `krizky-map` (`"site.map.leaflet.js is not configured; map will not work"`).
- Chování buildu se nemění. Varování nic nezastaví a vygenerované HTML, JSON i konfigurace jsou stejné jako dnes.
- Každé varování se vypíše jednou za build, ne jednou za vykreslenou stránku stránkování.
- V `docs/configuration.md` přibude krátká poznámka, že plugin při chybné konfiguraci varuje v logu. Platí pravidlo docs-sync.

**Akceptace:**
- Pro každý z případů 1–5 existuje test v pytestu (`caplog`), který ověří, že se varování objeví právě jednou.
- Test na platné konfiguraci ze stávajících fixtures ověří, že se žádné varování neobjeví.
- `scripts/verify` projde.

## Mimo rozsah (rozhodnuto 2026-11-09)

- **`from __future__ import annotations`:** zamítnuto, guidelines ho zakazují.
- **Přesun `pagination_window` a `pagination_boundary` k jednotlivým stránkám:** zamítnuto. `site.pagination_*` sdílí stránkování v core (`krizky/site.py:139`) a JS stránkování má fungovat stejně.
- **`PLAN.md`:** zamítnuto, v tomhle repu je záměrně v `.gitignore`.
- **`CLAUDE.md`:** hotovo v PR #1.
- **Napojení na `sources.photos.base_url` a konsolidace `_copy_assets` a registrace šablon do core:** odloženo do běhu přes víc rep, spolu s `krizky-map`.
- **Volitelné nálezy** (české texty stránkování, rozdělení testů, `docs/`): ne.

## Poznámky pro plánovače

- Obě části mění `krizky_filters/plugin.py` a `tests/test_filter_plugin.py`, takže poběží za sebou. Přejmenování je menší.
- Varování se nejspíš hodí do `extra_template_vars`, který prochází konfiguraci filtrů všech stránek najednou. `inject_body_end` se volá pro každou vykreslenou stránku a varování by se v něm opakovala. Ověř to v kódu core (`krizky/`), kde se hooky volají.
