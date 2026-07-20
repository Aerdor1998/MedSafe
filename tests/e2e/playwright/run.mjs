// =============================================================================
// MedSafe — Suite E2E de frontend (Playwright + Chromium headless)
// 21 testes: auth, wizard, análise crítica (nitrato×PDE5), guardrail HITL,
// export de laudo, tema, logout, responsivo (390×844), a11y básico e
// fila HITL (nav gated por hitl_enabled, listagem e aprovação → resume).
//
// Recriação versionada da suite validada em 2026-07-16 (18/18 PASS), que
// vivia em /tmp/medsafe_e2e e foi perdida. Lições preservadas:
//  - Visibilidade via getBoundingClientRect (offsetParent falha em fixed).
//  - waitResult "v4": só considera resultado quando #step-4 está visível E
//    #risk-label tem texto real (≠ placeholder "Calculando").
//
// Uso:
//   E2E_EMAIL=... E2E_PASSWORD=... npm test
//   (E2E_BASE_URL opcional; default https://localhost via nginx)
// =============================================================================
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BASE = process.env.E2E_BASE_URL || 'https://localhost';
const EMAIL = process.env.E2E_EMAIL;
const PASSWORD = process.env.E2E_PASSWORD;
const SHOTS = path.join(__dirname, 'shots');
const ANALYSIS_TIMEOUT = 180_000; // análise LLM leva ~15-30s; margem p/ cold start

if (!EMAIL || !PASSWORD) {
  console.error('Defina E2E_EMAIL e E2E_PASSWORD (conta physician de smoke test do stack local).');
  process.exit(2);
}

fs.mkdirSync(SHOTS, { recursive: true });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

async function waitFor(fn, { timeout = 15_000, interval = 250, label = 'condição' } = {}) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) {
    let ok = false;
    try { ok = await fn(); } catch { /* tenta de novo */ }
    if (ok) return true;
    await sleep(interval);
  }
  throw new Error(`timeout (${timeout}ms) esperando: ${label}`);
}

// Visibilidade robusta: classe .hidden do app + display/visibility + bounding
// rect não-nulo. NÃO usar offsetParent (retorna null p/ position:fixed).
const isVisible = (page, sel) => page.evaluate((s) => {
  const el = document.querySelector(s);
  if (!el || el.classList.contains('hidden')) return false;
  const st = getComputedStyle(el);
  if (st.display === 'none' || st.visibility === 'hidden') return false;
  const r = el.getBoundingClientRect();
  return r.width > 0 && r.height > 0;
}, sel);

const waitVisible = (page, sel, timeout = 15_000) =>
  waitFor(() => isVisible(page, sel), { timeout, label: `${sel} visível` });

// waitResult v4: condição terminal = step-4 visível E risk-label com rect
// não-nulo E texto real (≠ '' e ≠ 'Calculando'). Versões anteriores aceitavam
// banner HITL OU risk-label como terminal e geravam falsos resultados.
const waitResult = (page, timeout = ANALYSIS_TIMEOUT) =>
  waitFor(() => page.evaluate(() => {
    const vis = (s) => {
      const el = document.querySelector(s);
      if (!el || el.classList.contains('hidden')) return false;
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    };
    if (!vis('#step-4') || !vis('#risk-label')) return false;
    const txt = (document.querySelector('#risk-label').textContent || '').trim();
    return txt !== '' && txt.toLowerCase() !== 'calculando';
  }), { timeout, interval: 500, label: 'resultado da análise (step-4 + risk-label real)' });

const text = (page, sel) =>
  page.evaluate((s) => (document.querySelector(s)?.textContent || '').trim(), sel);

// =============================================================================
// Runner
// =============================================================================
async function main() {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    ignoreHTTPSErrors: true, // nginx local usa certificado self-signed
    viewport: { width: 1440, height: 900 },
    acceptDownloads: true,
  });
  const page = await ctx.newPage();

  const tests = [];
  const test = (id, name, fn) => tests.push({ id, name, fn });

  // --- Carga e saúde -------------------------------------------------------
  test('T01', 'Página carrega e step-1 visível', async () => {
    await page.goto(BASE, { waitUntil: 'domcontentloaded' });
    await waitVisible(page, '#step-1');
    const title = await page.title();
    assert(/medsafe/i.test(title), `title inesperado: "${title}"`);
  });

  test('T02', 'Backend saudável via /healthz (proxy nginx)', async () => {
    const ok = await page.evaluate(() => fetch('/healthz').then((r) => r.ok).catch(() => false));
    assert(ok, '/healthz não retornou 2xx');
  });

  // --- Autenticação --------------------------------------------------------
  test('T03', 'Modal de login abre pelo chip', async () => {
    await page.click('#auth-chip button');
    await waitVisible(page, '#auth-modal');
  });

  test('T04', 'Login vazio é bloqueado no cliente', async () => {
    await page.fill('#auth-email', '');
    await page.fill('#auth-password', '');
    await page.click('#auth-submit');
    await waitVisible(page, '#auth-error');
    assert(await isVisible(page, '#auth-modal'), 'modal fechou com campos vazios');
  });

  test('T05', 'Credenciais inválidas mostram erro da API', async () => {
    await page.fill('#auth-email', EMAIL);
    await page.fill('#auth-password', 'senha-errada-e2e-123');
    await page.click('#auth-submit');
    await waitFor(async () => {
      if (!(await isVisible(page, '#auth-error'))) return false;
      return /incorret|bloqueada|tentativas|falha/i.test(await text(page, '#auth-error'));
    }, { label: 'mensagem de erro da API no #auth-error' });
  });

  test('T06', 'Login válido fecha modal e mostra sessão no chip', async () => {
    await page.fill('#auth-password', PASSWORD);
    await page.click('#auth-submit');
    await waitFor(async () => {
      const modalHidden = !(await isVisible(page, '#auth-modal'));
      const hasLogout = await page.evaluate(() =>
        !!document.querySelector('#auth-chip [aria-label="Sair da conta"]'));
      return modalHidden && hasLogout;
    }, { label: 'modal fechado + botão Sair no chip' });
  });

  // --- Wizard: análise crítica (nitrato × PDE5) ----------------------------
  test('T07', 'Step 1: perfil do paciente + medicamento em uso', async () => {
    await page.fill('#age', '68');
    // Peso único por run: o backend deduplica análises por hash do payload
    // (medication+age+weight+meds+conditions). Payload repetido devolve o
    // resultado cacheado SEM criar triage nova — e T20/T21 dependem de a
    // fila HITL receber cards novos neste run.
    const uniqueWeight = (70 + (Date.now() % 30000) / 1000).toFixed(3);
    await page.fill('#weight', uniqueWeight);
    await page.fill('#conditions', 'hipertensão arterial; angina estável');
    await page.fill('#current-med-input', 'Monocordil 20mg');
    await page.press('#current-med-input', 'Enter');
    await waitFor(async () => (await text(page, '#current-meds-count')) === '1',
      { label: 'contador de medicamentos = 1' });
    const list = await text(page, '#current-meds-list');
    assert(/monocordil/i.test(list), 'Monocordil não apareceu na lista');
  });

  test('T08', 'Continuar avança para o step 2', async () => {
    await page.click('[onclick="nextStep(2)"]');
    await waitVisible(page, '#step-2');
    assert(!(await isVisible(page, '#step-1')), 'step-1 continua visível');
  });

  test('T09', 'Analisar segurança inicia o step 3 (processando)', async () => {
    await page.fill('#medication-search', 'Sildenafila 50mg');
    await page.click('[onclick="startAnalysis()"]');
    await waitVisible(page, '#step-3');
  });

  test('T10', 'Análise conclui: step-4 com risco real (waitResult v4)', async () => {
    await waitResult(page);
  });

  test('T11', 'Interação crítica detectada (nitrato × PDE5)', async () => {
    const label = await text(page, '#risk-label');
    assert(/cr[íi]t/i.test(label), `risk-label não é crítico: "${label}"`);
    const scoreTxt = await text(page, '#risk-score');
    const score = parseFloat(scoreTxt.replace(',', '.'));
    assert(Number.isFinite(score) && score >= 7, `risk-score fora da faixa crítica: "${scoreTxt}"`);
    const nInter = parseInt(await text(page, '#interaction-count'), 10);
    assert(nInter >= 1, `esperava ≥1 interação, obtive "${nInter}"`);
  });

  test('T12', 'Exportar laudo baixa JSON válido', async () => {
    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 15_000 }),
      page.click('[onclick="downloadReport()"]'),
    ]);
    assert(/^medsafe-report-.*\.json$/.test(download.suggestedFilename()),
      `nome inesperado: ${download.suggestedFilename()}`);
    const dest = path.join(SHOTS, 'laudo-e2e.json');
    await download.saveAs(dest);
    const raw = fs.readFileSync(dest, 'utf-8');
    assert(raw.length > 500, `laudo muito pequeno (${raw.length} bytes)`);
    const laudo = JSON.parse(raw);
    assert(laudo.risk_level, 'laudo sem risk_level');
    assert(laudo.medication_analyzed, 'laudo sem medication_analyzed');
  });

  test('T13', 'Nova análise reseta o wizard para o step 1', async () => {
    await page.click('[onclick="resetAnalysis()"]');
    await waitVisible(page, '#step-1');
  });

  // --- Guardrail HITL: medicamento desconhecido -----------------------------
  test('T14', 'Medicamento desconhecido aciona banner de revisão humana', async () => {
    await page.click('[onclick="nextStep(2)"]');
    await waitVisible(page, '#step-2');
    await page.fill('#medication-search', 'Blorfazina 10mg');
    await page.click('[onclick="startAnalysis()"]');
    await waitResult(page);
    await waitVisible(page, '#human-review-banner');
    const nReasons = await page.evaluate(() =>
      document.querySelectorAll('#human-review-reasons li').length);
    assert(nReasons >= 1, 'banner HITL sem motivos listados');
  });

  // --- Tema, logout, responsivo, a11y --------------------------------------
  test('T15', 'Tema alterna e persiste em localStorage', async () => {
    await page.click('.theme-toggle');
    const v1 = await page.evaluate(() => localStorage.getItem('medsafe-theme'));
    await page.click('.theme-toggle');
    const v2 = await page.evaluate(() => localStorage.getItem('medsafe-theme'));
    assert(['dark', 'light'].includes(v1) && ['dark', 'light'].includes(v2) && v1 !== v2,
      `tema não alternou: ${v1} → ${v2}`);
  });

  test('T16', 'Logout devolve o chip ao estado "Entrar"', async () => {
    await page.click('#auth-chip [aria-label="Sair da conta"]');
    await waitFor(() => page.evaluate(() =>
      !!document.querySelector('#auth-chip [aria-label="Entrar na conta"]')),
      { label: 'chip com botão Entrar' });
  });

  test('T17', 'Mobile 390×844 renderiza sem overflow horizontal', async () => {
    const mctx = await browser.newContext({
      ignoreHTTPSErrors: true,
      viewport: { width: 390, height: 844 },
    });
    const mpage = await mctx.newPage();
    try {
      await mpage.goto(BASE, { waitUntil: 'domcontentloaded' });
      await waitVisible(mpage, '#step-1');
      // Estado estável, não snapshot: logo após o load, blobs decorativos
      // ainda sem o clip do CSS inflam scrollWidth transitoriamente.
      await waitFor(() => mpage.evaluate(() =>
        document.documentElement.scrollWidth <= window.innerWidth + 1),
        { timeout: 10_000, label: 'layout mobile sem overflow horizontal' });
    } finally {
      await mctx.close();
    }
  });

  test('T18', 'A11y básico: aria-labels, labels associados e alt', async () => {
    const missing = await page.evaluate(() => {
      const out = [];
      if (!document.querySelector('.theme-toggle')?.getAttribute('aria-label')) out.push('theme-toggle sem aria-label');
      if (!document.querySelector('[onclick="addCurrentMed()"]')?.getAttribute('aria-label')) out.push('botão add-med sem aria-label');
      for (const id of ['age', 'weight', 'allergies', 'medication-search']) {
        if (!document.querySelector(`label[for="${id}"]`)) out.push(`sem label[for=${id}]`);
      }
      if (!document.querySelector('#preview-img')?.getAttribute('alt')) out.push('preview-img sem alt');
      return out;
    });
    assert(missing.length === 0, `violações: ${missing.join('; ')}`);
  });

  // --- Fila HITL (UI de revisão humana) ------------------------------------
  test('T19', 'Re-login e nav "Revisão HITL" visível (hitl_enabled)', async () => {
    await page.click('#auth-chip button');
    await waitVisible(page, '#auth-modal');
    await page.fill('#auth-email', EMAIL);
    await page.fill('#auth-password', PASSWORD);
    await page.click('#auth-submit');
    await waitFor(async () => {
      const modalHidden = !(await isVisible(page, '#auth-modal'));
      const hasLogout = await page.evaluate(() =>
        !!document.querySelector('#auth-chip [aria-label="Sair da conta"]'));
      return modalHidden && hasLogout;
    }, { label: 'sessão restabelecida para a fila HITL' });
    await waitFor(() => isVisible(page, '#nav-hitl'),
      { label: '#nav-hitl visível (backend com hitl_enabled)' });
  });

  test('T20', 'Fila HITL abre e lista pendência com notas + ações', async () => {
    await page.click('#nav-hitl');
    await waitVisible(page, '#step-hitl');
    // T14 deixou uma análise awaiting_review (Blorfazina) — a fila não pode
    // estar vazia neste ponto do run. IMPORTANTE: contar apenas cards REAIS
    // (com .hitl-notes) — o <li> "Carregando fila…" é placeholder.
    await waitFor(() => page.evaluate(() =>
      document.querySelectorAll('#hitl-list li .hitl-notes').length >= 1),
      { timeout: 20_000, label: '≥1 card pendente (real) na fila HITL' });
    const badge = parseInt(await text(page, '#hitl-count'), 10);
    assert(badge >= 1, `badge #hitl-count deveria ser ≥1, obtive "${badge}"`);
    const hasActions = await page.evaluate(() => {
      const li = document.querySelector('#hitl-list li');
      return !!li?.querySelector('.hitl-notes') && li.querySelectorAll('button').length >= 2;
    });
    assert(hasActions, 'card sem textarea de notas ou sem botões Aprovar/Rejeitar');
  });

  test('T21', 'Aprovar pendência retoma o workflow e atualiza a fila', async () => {
    // Conta apenas cards reais (placeholder "Carregando fila…" não tem notas).
    const countCards = () => page.evaluate(() =>
      document.querySelectorAll('#hitl-list li .hitl-notes').length);
    const before = await countCards();
    assert(before >= 1, 'fila sem cards reais no início do T21');
    // Aprova o card MAIS RECENTE (o gerado pelo T14 neste run): cards antigos
    // de stacks anteriores podem não ter checkpoint p/ retomar o workflow.
    const idx = await page.evaluate(() => {
      const cards = [...document.querySelectorAll('#hitl-list li')]
        .filter((li) => li.querySelector('.hitl-notes'));
      let best = 0, bestWhen = '';
      cards.forEach((li, i) => {
        const when = li.querySelector('.font-mono')?.textContent || '';
        if (when > bestWhen) { bestWhen = when; best = i; }
      });
      return best;
    });
    const card = `#hitl-list li:nth-child(${idx + 1})`;
    await page.fill(`${card} .hitl-notes`, 'Aprovado via suite E2E');
    await page.click(`${card} .btn-primary`);
    await waitFor(() => page.evaluate((sel) =>
      /workflow retomado/i.test(document.querySelector(sel)?.textContent || ''),
      // O approve re-executa o grafo (Clinical+Safety+HITL) de forma síncrona:
      // 21–60s observados. 120s dá folga sem mascarar travamento real.
      card), { timeout: 120_000, label: 'confirmação "workflow retomado" no card' });
    // Refresh automático (1,5s) remove o card resolvido.
    await waitFor(async () => {
      const n = await countCards();
      return n < before || (before === 1 && (await isVisible(page, '#hitl-empty')));
    }, { timeout: 20_000, label: `fila reduzida para < ${before} cards` });
  });

  // --- Execução -------------------------------------------------------------
  let pass = 0;
  for (const t of tests) {
    const t0 = Date.now();
    try {
      await t.fn();
      pass++;
      console.log(`PASS ${t.id} ${t.name} (${((Date.now() - t0) / 1000).toFixed(1)}s)`);
    } catch (e) {
      console.log(`FAIL ${t.id} ${t.name} — ${e.message}`);
      try {
        await page.screenshot({ path: path.join(SHOTS, `${t.id}-fail.png`), fullPage: true });
      } catch { /* página pode estar fechada */ }
    }
  }

  console.log(`\n${pass}/${tests.length} PASS`);
  await browser.close();
  process.exit(pass === tests.length ? 0 : 1);
}

main().catch((e) => {
  console.error('Erro fatal do runner:', e);
  process.exit(1);
});
