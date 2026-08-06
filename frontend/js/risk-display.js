/**
 * MedSafe — fonte única de verdade para exibição de risco.
 * Enum do backend (state.py RiskLevel): critical | high | medium | low.
 */
(function (global) {
  'use strict';

  const RISK_CONFIG = {
    critical: { label: 'Crítico' },
    high:     { label: 'Alto' },
    medium:   { label: 'Moderado' },
    low:      { label: 'Baixo' }
  };

  const UNKNOWN = { label: 'Indeterminado' };

  function riskDisplay(riskLevel, backendScore) {
    const known = typeof riskLevel === 'string' &&
      Object.prototype.hasOwnProperty.call(RISK_CONFIG, riskLevel);
    const config = known ? RISK_CONFIG[riskLevel] : UNKNOWN;
    const hasScore = known && typeof backendScore === 'number' &&
      Number.isFinite(backendScore);
    return {
      level: known ? riskLevel : 'unknown',
      label: config.label,
      scoreText: hasScore ? backendScore.toFixed(1) : '--'
    };
  }

  const api = { riskDisplay };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  } else {
    global.MedSafeRisk = api;
  }
})(typeof window !== 'undefined' ? window : globalThis);
