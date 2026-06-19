import assert from 'node:assert/strict';

import {
  CHART_CONFIG,
  DASHBOARD_CHART_BASE_SPEC,
  TRANSPARENT_CHART_BACKGROUND,
} from './dashboard.constants.js';

assert.equal(
  DASHBOARD_CHART_BASE_SPEC.background,
  TRANSPARENT_CHART_BACKGROUND,
  'dashboard chart specs must override VChart theme backgrounds',
);

assert.equal(
  CHART_CONFIG.mode,
  'desktop-browser',
  'dashboard chart config should keep the desktop browser render mode',
);
