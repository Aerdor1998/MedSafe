/**
 * Tailwind CSS Configuration
 * Configuração de tema customizado para MedSafe
 */

// Verificar se Tailwind está carregado
if (typeof tailwind !== 'undefined') {
    tailwind.config = {
        theme: {
            extend: {
                fontFamily: {
                    sans: ['Inter', 'sans-serif'],
                },
                colors: {
                    dark: {
                        900: '#0a0a0f',
                        800: '#12121a',
                        700: '#1a1a25',
                        600: '#252532',
                        500: '#32324a',
                    },
                    accent: {
                        orange: '#f97316',
                        coral: '#ff6b6b',
                        teal: '#14b8a6',
                        blue: '#3b82f6',
                        purple: '#8b5cf6',
                    }
                }
            }
        }
    };
} else {
    console.warn('Tailwind CDN não carregado. Usando estilos padrão.');
}
