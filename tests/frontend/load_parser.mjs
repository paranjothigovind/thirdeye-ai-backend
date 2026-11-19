// Loads app/ui/static/sse-parser.js the way a browser does: as a classic script
// evaluated in a global scope, then returns its SSEParser global.
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

export function loadSSEParser() {
    const code = readFileSync(new URL('../../app/ui/static/sse-parser.js', import.meta.url), 'utf8');
    const sandbox = { TextDecoder };
    vm.createContext(sandbox);
    vm.runInContext(code, sandbox, { filename: 'sse-parser.js' });
    return sandbox.SSEParser;
}
