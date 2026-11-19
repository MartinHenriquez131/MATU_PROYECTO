// MATU-79: lint de la app web, en el formato plano de ESLint 9.
// ESLint 9 y no 10 porque eslint-plugin-jsx-a11y 6.10.2, la versión más nueva, solo acepta hasta ESLint 9.
// Reglas: las recomendadas de JavaScript y de TypeScript, las dos reglas clásicas de react-hooks (reglas de los hooks y
// dependencias de los efectos) y las recomendadas de jsx-a11y, porque la accesibilidad es requisito del proyecto
// (estrategia de pruebas, sección 7). Las reglas del React Compiler que trae react-hooks 7 no se activan: MATU no usa
// el compilador.
import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import reactHooks from 'eslint-plugin-react-hooks'
import jsxA11y from 'eslint-plugin-jsx-a11y'

export default tseslint.config(
  {
    // Generados (npm run contrato y contrato:familia) y salidas de la compilación
    ignores: ['dist/', 'node_modules/', 'coverage/', '**/*.openapi.ts'],
  },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended, jsxA11y.flatConfigs.recommended],
    plugins: { 'react-hooks': reactHooks },
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      // Igual que tsc con noUnusedLocals y noUnusedParameters: un guion bajo al inicio marca lo que se deja a propósito
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      // Los espacios duros (U+00A0 y U+202F) van a propósito en los textos, para que «1 minuto» o «$69.000» no se
      // corten al final de una línea. Se siguen marcando los que aparezcan en el código
      'no-irregular-whitespace': [
        'error',
        { skipStrings: true, skipTemplates: true, skipComments: true, skipRegExps: true, skipJSXText: true },
      ],
      // Ajustes a jsx-a11y para patrones de accesibilidad que MATU usa a propósito (revisados el 18-11, MATU-79):
      // · role="list" en ul y ol: Safari quita la semántica de lista cuando no hay viñetas (compartido/ui/Indice.tsx)
      // · role="rowgroup" y role="row" en tablas mostradas como bloques bajo @xl/main: display: block les quita la
      //   semántica de tabla, y los roles (también role="cell" en td) la devuelven (privacidad/Documento.tsx)
      'jsx-a11y/no-redundant-roles': [
        'error',
        { nav: ['navigation'], ul: ['list'], ol: ['list'], thead: ['rowgroup'], tbody: ['rowgroup'] },
      ],
      'jsx-a11y/no-interactive-element-to-noninteractive-role': [
        'error',
        { tr: ['none', 'presentation', 'row'], td: ['cell'], canvas: ['img'] },
      ],
      // · Escape delegado: un formulario o un grupo escucha onKeyDown para cerrar el editor desde cualquiera de sus
      //   campos. No vuelve interactivo al contenedor. Lo demás queda igual a la recomendada
      'jsx-a11y/no-noninteractive-element-interactions': [
        'error',
        {
          handlers: ['onClick', 'onError', 'onLoad', 'onMouseDown', 'onMouseUp', 'onKeyPress', 'onKeyDown', 'onKeyUp'],
          alert: ['onKeyUp', 'onKeyDown', 'onKeyPress'],
          body: ['onError', 'onLoad'],
          dialog: ['onKeyUp', 'onKeyDown', 'onKeyPress'],
          iframe: ['onError', 'onLoad'],
          img: ['onError', 'onLoad'],
          form: ['onKeyDown'],
          // Las opciones van por elemento: div cubre el role="group" de los editores de Insumos.tsx
          div: ['onKeyDown'],
        },
      ],
      // · Las casillas llevan el texto en dos span anidados (título y ayuda): hace falta mirar tres niveles adentro
      'jsx-a11y/label-has-associated-control': ['error', { depth: 3 }],
    },
  },
  {
    // El service worker (MATU-55) corre fuera de la página: sus globales son las del worker
    files: ['public/sw.js'],
    extends: [js.configs.recommended],
    languageOptions: {
      sourceType: 'script',
      globals: { self: 'readonly', URL: 'readonly' },
    },
  },
)
