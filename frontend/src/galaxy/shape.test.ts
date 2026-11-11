import { expect, test } from 'vitest';
import { hash2 } from './noise';
import { density, validLayout } from './shape';
import type { Layout } from './shape';

const at = (shape: Layout['shape'], params: Layout['params']) => density({ shape, cx: 0, cy: 0, radius: 1, squash: 740, params });

test('the noise hash matches the server bit for bit', () => {
  // Same values as backend tests/test_galaxy_shapes.py (app/galaxy/shapes.py).
  expect(hash2(0, 0, 0)).toBe(0.05130852316506207);
  expect(hash2(-3, 7, 11)).toBe(0.8753199882339686);
  expect(hash2(123, -45, 998)).toBe(0.8319499371573329);
});

test('the backdrop density is the one the server placed the systems with', () => {
  // Reference values computed by app.galaxy.shapes.density for the same parameters.
  const cases: [Layout['shape'], Layout['params'], number[]][] = [
    ['spiral2', { ns: 100, rot: 1234 }, [0.18899927444018488, 0.6089440503397316, 0.048055923318289506]],
    ['spiral4', { ns: 57, rot: 4000 }, [0.5348826297737594, 0.5834962755911425, 0.11369324141267519]],
    ['elliptical', { ns: 33, e: 800, rot: 900 }, [0.8046186930125849, 0.04717083221129526, 0.4468946817717093]],
    ['irregular', { ns: 500, ox: 12000, oy: 34000, sx: 1000 }, [0.9075336882170351, 0, 0.14130323629017932]],
    ['clusters', { ns: 20, clusters: [[100, -200, 90], [-400, 300, 120]] }, [0.012005000777938311, 0.0045666316076221165, 1.0117426887958065]],
  ];
  for (const [shape, params, expected] of cases) {
    const f = at(shape, params);
    [[0.3, 0.2], [0.7, -0.4], [-0.35, 0.3]].forEach(([u, v], i) => expect(f(u, v)).toBeCloseTo(expected[i], 9));
  }
});

test('a layout is checked before it is drawn', () => {
  const layout = { shape: 'spiral2', cx: 3000, cy: 2300, radius: 2900, squash: 740, params: { ns: 40, rot: 100 } };
  expect(validLayout(layout)).toBe(true);
  expect(validLayout({ ...layout, shape: 'ring' })).toBe(false);
  expect(validLayout({ ...layout, radius: 0 })).toBe(false);
  expect(validLayout({ ...layout, cx: 1.5 })).toBe(false);
  expect(validLayout({ ...layout, params: { ns: 1, clusters: [[1, 2]] } })).toBe(false);
});
