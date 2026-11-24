import test from 'node:test';
import assert from 'node:assert/strict';
import { pure } from './load-filters.mjs';

const { parseSortParam, compareSortValues, sortRecords } = pure;

const OPTIONS = [
  { field: 'cena', label: 'Cena' },
  { field: 'plocha', label: 'Plocha' },
];

test('parseSortParam', () => {
  const cases = [
    ['cena', { field: 'cena', desc: false }],
    ['-cena', { field: 'cena', desc: true }],
    ['plocha', { field: 'plocha', desc: false }],
    ['neznamy', null],
    ['-neznamy', null],
    ['', null],
    [null, null],
    [undefined, null],
    ['-', null],
  ];
  for (const [raw, expected] of cases) {
    assert.deepEqual(parseSortParam(raw, OPTIONS), expected, `raw=${JSON.stringify(raw)}`);
  }
  assert.equal(parseSortParam('cena', []), null);
  assert.equal(parseSortParam('cena', null), null);
});

function sortedValues(values, desc) {
  return [...values].sort((a, b) => compareSortValues(a, b, desc));
}

test('compareSortValues: čísla a číselné řetězce', () => {
  assert.deepEqual(sortedValues([10, 2], false), [2, 10]);
  assert.deepEqual(sortedValues([2, 10], true), [10, 2]);
  assert.deepEqual(sortedValues(['10', '9.5'], false), ['9.5', '10']);
  assert.deepEqual(sortedValues([10, '9.5'], false), ['9.5', 10]);
});

test('compareSortValues: text s diakritikou bez ohledu na velikost', () => {
  // "čáp" a "cap" mají stejný klíč, proto si drží vstupní pořadí.
  assert.deepEqual(sortedValues(['dub', 'cap', 'čáp'], false), ['cap', 'čáp', 'dub']);
  assert.deepEqual(sortedValues(['dub', 'cap', 'Čáp'], false), ['cap', 'Čáp', 'dub']);
  assert.deepEqual(sortedValues(['cap', 'dub', 'čáp'], true), ['dub', 'cap', 'čáp']);
  assert.ok(compareSortValues('čáp', 'cap', false) === 0);
  assert.ok(compareSortValues('čáp', 'dub', false) < 0);
  assert.ok(compareSortValues('čáp', 'bob', false) > 0);
});

test('compareSortValues: smíšené číslo a text se porovná jako text', () => {
  assert.deepEqual(sortedValues(['b', '10'], false), ['10', 'b']);
  assert.ok(compareSortValues('9', 'a9', false) < 0);
});

test('compareSortValues: prázdné hodnoty vždy na konci', () => {
  const empties = [null, undefined, '', '   '];
  for (const desc of [false, true]) {
    for (const empty of empties) {
      assert.equal(compareSortValues(empty, 5, desc), 1);
      assert.equal(compareSortValues(5, empty, desc), -1);
      assert.equal(compareSortValues(empty, 'a', desc), 1);
      for (const other of empties) {
        assert.equal(compareSortValues(empty, other, desc), 0);
      }
    }
  }
});

test('sortRecords: čísla, prázdné hodnoty na konci v obou směrech', () => {
  const records = [
    { id: 1, cena: 10 },
    { id: 2, cena: null },
    { id: 3, cena: 2 },
    { id: 4 },
    { id: 5, cena: '' },
    { id: 6, cena: 7 },
  ];
  const ids = (list) => list.map((r) => r.id);
  assert.deepEqual(ids(sortRecords(records, { field: 'cena', desc: false })), [3, 6, 1, 2, 4, 5]);
  assert.deepEqual(ids(sortRecords(records, { field: 'cena', desc: true })), [1, 6, 3, 2, 4, 5]);
});

test('sortRecords: stabilita při shodě v obou směrech', () => {
  const records = [
    { id: 1, cena: 5 },
    { id: 2, cena: 3 },
    { id: 3, cena: 5 },
    { id: 4, cena: 3 },
  ];
  const ids = (list) => list.map((r) => r.id);
  assert.deepEqual(ids(sortRecords(records, { field: 'cena', desc: false })), [2, 4, 1, 3]);
  assert.deepEqual(ids(sortRecords(records, { field: 'cena', desc: true })), [1, 3, 2, 4]);
});

test('sortRecords: nemutuje vstup, pro null vrací vstupní pořadí', () => {
  const records = [{ cena: 3 }, { cena: 1 }, { cena: 2 }];
  const copy = [...records];
  const sorted = sortRecords(records, { field: 'cena', desc: false });
  assert.notEqual(sorted, records);
  assert.deepEqual(records, copy);
  const same = sortRecords(records, null);
  assert.notEqual(same, records);
  assert.deepEqual(same, copy);
});
