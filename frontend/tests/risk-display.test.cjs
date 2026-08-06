'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { riskDisplay } = require('../js/risk-display.js');

test('níveis válidos do enum do backend mapeiam para rótulos pt-BR corretos', () => {
  assert.equal(riskDisplay('critical').label, 'Crítico');
  assert.equal(riskDisplay('high').label, 'Alto');
  assert.equal(riskDisplay('medium').label, 'Moderado');
  assert.equal(riskDisplay('low').label, 'Baixo');
});

test('valores fora do enum rendem Indeterminado — nunca degradam para Baixo', () => {
  for (const bad of ['unknown', 'LOW', 'baixo', '', null, undefined, 7.5]) {
    const d = riskDisplay(bad);
    assert.equal(d.level, 'unknown', `level para ${String(bad)}`);
    assert.equal(d.label, 'Indeterminado', `label para ${String(bad)}`);
  }
});

test('nota vem do backend ou é omitida — nunca fabricada a partir do rótulo', () => {
  // score real do backend é exibido com 1 casa decimal
  assert.equal(riskDisplay('critical', 8.7).scoreText, '8.7');
  assert.equal(riskDisplay('low', 0).scoreText, '0.0');
  // sem score do backend: omite ('--'), inclusive para níveis válidos
  assert.equal(riskDisplay('critical').scoreText, '--');
  assert.equal(riskDisplay('low', null).scoreText, '--');
  // score inválido não vira número inventado
  assert.equal(riskDisplay('high', 'NaN').scoreText, '--');
  assert.equal(riskDisplay('unknown', 9.9).scoreText, '--');
});
