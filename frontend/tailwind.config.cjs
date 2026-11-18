// Rebuild from the repository root with the command in docs/RUNBOOK.md.
module.exports = {
    content: { relative: true, files: ['./index.html', './js/risk-display.js'] },
    darkMode: 'class',
    theme: {
        extend: {
            fontFamily: {
                display: ['"Bricolage Grotesque"', 'ui-sans-serif', 'sans-serif'],
                sans: ['"Instrument Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
                mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
            },
            colors: {
                // Cores dirigidas por CSS vars: os MESMOS utilitários que o
                // script da aplicação gera dinamicamente (text-slate-*,
                // bg-brand-*/15, violet-*, red-*) mudam junto com o tema.
                brand: {
                    DEFAULT: 'rgb(var(--c-teal) / <alpha-value>)',
                    teal: 'rgb(var(--c-teal) / <alpha-value>)',
                    cyan: 'rgb(var(--c-cyan) / <alpha-value>)',
                    emerald: 'rgb(var(--c-emerald) / <alpha-value>)',
                    amber: 'rgb(var(--c-amber) / <alpha-value>)',
                    rose: 'rgb(var(--c-rose) / <alpha-value>)',
                },
                violet: {
                    400: 'rgb(var(--c-violet-400) / <alpha-value>)',
                    500: 'rgb(var(--c-violet-500) / <alpha-value>)',
                },
                red: {
                    400: 'rgb(var(--c-red-400) / <alpha-value>)',
                    500: 'rgb(var(--c-red-500) / <alpha-value>)',
                },
                slate: {
                    200: 'rgb(var(--tx-1) / <alpha-value>)',
                    300: 'rgb(var(--tx-2) / <alpha-value>)',
                    400: 'rgb(var(--tx-3) / <alpha-value>)',
                    500: 'rgb(var(--tx-4) / <alpha-value>)',
                    600: 'rgb(var(--tx-5) / <alpha-value>)',
                },
                surface: {
                    DEFAULT: 'rgb(var(--sf-1) / <alpha-value>)',
                    600: 'rgb(var(--sf-3) / <alpha-value>)',
                    700: 'rgb(var(--sf-2) / <alpha-value>)',
                },
            },
        }
    }
};
