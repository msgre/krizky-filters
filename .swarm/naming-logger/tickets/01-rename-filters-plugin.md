---
id: "01"
slug: rename-filters-plugin
title: Přejmenovat FilterPlugin na FiltersPlugin
status: pending
depends_on: []
files:
  - krizky_filters/plugin.py
  - tests/test_filter_plugin.py
attempts: 0
pr: ""
---

## Cíl
Jméno třídy pluginu má odpovídat balíčku `krizky_filters`, stejně jako u ostatních pluginů (`MapPlugin`/`krizky_map`, `SharePlugin`/`krizky_share`). Třídu `FilterPlugin` v `krizky_filters/plugin.py` přejmenuj na `FiltersPlugin`, včetně instance `plugin = FiltersPlugin()` a všech odkazů v testech. Viz specifikace `.swarm/naming-logger/spec.md`, část 1.

## Akceptační kritéria
- Třída v `krizky_filters/plugin.py` se jmenuje `FiltersPlugin` a modulová instance je `plugin = FiltersPlugin()`.
- Alias `FilterPlugin` nevznikne (žádné `FilterPlugin = FiltersPlugin`).
- Entry point v `pyproject.toml` se nemění, dál odkazuje na instanci `plugin`.
- `git grep -n FilterPlugin -- ':!.swarm'` nic nenajde. Výskyty ve specifikaci a ticketech v `.swarm/` se nepočítají, ty se nemění.
- `scripts/verify` skončí s exit 0.

## Testy
- Nejdřív v `tests/test_filter_plugin.py` změň import na `from krizky_filters.plugin import FiltersPlugin, ...` a všechna `FilterPlugin()` na `FiltersPlugin()`. Testy pak selžou na ImportError, dokud se nepřejmenuje třída.
- Nový test není potřeba. Volitelně jednoduchý test, že `krizky_filters.plugin.plugin` je instance `FiltersPlugin`.

## Poznámky
- Jde čistě o přejmenování, chování se nemění.
- `docs/`, `README.md` ani `CLAUDE.md` jméno třídy dnes neobsahují (ověřeno přes `git grep`). Pokud tam přesto nějaký výskyt najdeš, oprav ho taky.
- Ticket 02 na tomhle přejmenování staví (nové testy budou používat `FiltersPlugin`).

## Otázky
