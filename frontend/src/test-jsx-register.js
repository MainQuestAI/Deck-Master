import { register } from 'node:module';

// Node's test runner does not transform the Vite JSX graph.
register('./test-jsx-hooks.js', import.meta.url);
