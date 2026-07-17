# Suite E2E de frontend — MedSafe (Playwright)

18 testes de ponta a ponta contra o stack local completo (nginx + API + worker +
Ollama), cobrindo: autenticação, wizard do paciente, análise de interação
crítica (nitrato × PDE5 → CRÍTICO), guardrail HITL para medicamento
desconhecido, export de laudo JSON, tema claro/escuro, logout, layout mobile
(390×844) e a11y básico.

## Pré-requisitos

- Stack local no ar: `docker compose up -d` (frontend servido em `https://localhost`)
- Node.js 18+ e Chromium do Playwright (`npx playwright install chromium` se necessário)
- Uma conta ativa no banco local (a suite usa a conta *physician* de smoke test)

## Como rodar

```bash
cd tests/e2e/playwright
npm install
E2E_EMAIL='<email da conta de teste>' E2E_PASSWORD='<senha>' npm test
```

Variáveis:

| Var | Default | Descrição |
| --- | --- | --- |
| `E2E_EMAIL` | — (obrigatória) | E-mail da conta de teste (não commitar) |
| `E2E_PASSWORD` | — (obrigatória) | Senha da conta de teste (não commitar) |
| `E2E_BASE_URL` | `https://localhost` | URL do frontend (nginx, cert self-signed) |

Saída esperada: `18/18 PASS` e exit code 0. Screenshots de falhas ficam em
`shots/` (ignorado pelo git).

## Lições incorporadas (não regredir)

- **Visibilidade**: usar `getBoundingClientRect()` + classe `.hidden`;
  `offsetParent` retorna `null` para elementos `position: fixed` (modal) e
  gera falso negativo.
- **Condição terminal da análise (waitResult v4)**: exigir `#step-4` visível
  **e** `#risk-label` com texto real (≠ placeholder `Calculando`). Aceitar o
  banner HITL ou o label sozinhos como condição terminal causa corrida com o
  render e resultados falsos.
- **Análises reais demoram ~15–30s** (LLM local); timeout de 180s por análise.
