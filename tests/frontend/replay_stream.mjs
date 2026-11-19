// Replays a captured SSE body through the browser parser in random-size byte
// fragments and prints the parsed events as JSON.
// Usage: node replay_stream.mjs <body-file> <seed>
import { readFileSync } from 'node:fs';
import { loadSSEParser } from './load_parser.mjs';

const { createSSEParser } = loadSSEParser();

const bytes = readFileSync(process.argv[2]);
let seed = Number(process.argv[3] || 1);
const random = () => {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    return seed / 2147483648;
};

const events = [];
const parser = createSSEParser((event) => events.push(event));
let offset = 0;
while (offset < bytes.length) {
    const size = 1 + Math.floor(random() * 7);
    parser.pushBytes(bytes.subarray(offset, offset + size));
    offset += size;
}
parser.end();
process.stdout.write(JSON.stringify(events));
