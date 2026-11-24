import test from 'node:test';
import assert from 'node:assert/strict';
import { pure } from './load-filters.mjs';

const { toNumber, parseRangeValue, serializeRange, matchesRange, rangeExtent } = pure;

test('toNumber', () => {
  const cases = [
    [52, 52],
    [0, 0],
    [52.5, 52.5],
    ['52.5', 52.5],
    ['3000000', 3000000],
    [null, null],
    [undefined, null],
    ['', null],
    ['abc', null],
    [true, null],
    [NaN, null],
    [Infinity, null],
  ];
  for (const [input, expected] of cases) {
    assert.equal(toNumber(input), expected, `toNumber(${String(input)})`);
  }
});

test('parseRangeValue a serializeRange', () => {
  const cases = [
    ['3000000-5000000', { min: 3000000, max: 5000000 }, '3000000-5000000'],
    ['3000000-', { min: 3000000, max: null }, '3000000-'],
    ['-5000000', { min: null, max: 5000000 }, '-5000000'],
    ['52.5-60', { min: 52.5, max: 60 }, '52.5-60'],
    ['5-3', { min: 3, max: 5 }, '3-5'],
    ['003000000-', { min: 3000000, max: null }, '3000000-'],
    ['abc', null, null],
    ['1-2-3', null, null],
    ['-', null, null],
    ['', null, null],
    ['-5-', null, null],
  ];
  for (const [raw, parsed, serialized] of cases) {
    const result = parseRangeValue(raw);
    assert.deepEqual(result, parsed, `parseRangeValue(${JSON.stringify(raw)})`);
    if (parsed) {
      assert.equal(serializeRange(result), serialized);
    }
  }
  assert.equal(serializeRange({ min: null, max: null }), '');
});

test('matchesRange', () => {
  const both = { min: 10, max: 20 };
  const cases = [
    [10, both, true],
    [20, both, true],
    [15, both, true],
    [9.9, both, false],
    [20.1, both, false],
    [null, both, false],
    [undefined, both, false],
    ['15', both, true],
    ['abc', both, false],
    [5, { min: 3, max: null }, true],
    [2, { min: 3, max: null }, false],
    [5, { min: null, max: 7 }, true],
    [8, { min: null, max: 7 }, false],
    [null, { min: 3, max: null }, false],
  ];
  for (const [value, range, expected] of cases) {
    assert.equal(
      matchesRange(value, range),
      expected,
      `${String(value)} v ${JSON.stringify(range)}`
    );
  }
});

test('rangeExtent', () => {
  const records = [{ p: 5 }, { p: null }, { p: 'x' }, { p: '12.5' }, {}, { p: 2 }];
  assert.deepEqual(rangeExtent(records, 'p'), { min: 2, max: 12.5 });
  assert.equal(rangeExtent([], 'p'), null);
  assert.equal(rangeExtent([{ p: null }, { p: 'abc' }], 'p'), null);
});
