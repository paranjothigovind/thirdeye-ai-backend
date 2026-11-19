// Tests for app/ui/static/sse-parser.js (run: node --test "tests/frontend/*.test.mjs")
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadSSEParser } from './load_parser.mjs';

const { createSSEParser } = loadSSEParser();

const STREAM =
    ': keep-alive\n\n' +
    'data: {"chunk": "Observe the ", "type": "content"}\n\n' +
    ': keep-alive\n\n' +
    'data: {"chunk": "natural breath.", "type": "content"}\n\n' +
    'data: {"citations": [{"title": "Guide", "reference": "page 3"}], "type": "citations"}\n\n' +
    'data: [DONE]\n\n';

function collect(feed) {
    const events = [];
    // JSON round-trip: events are created in the sandbox realm (different prototypes)
    const parser = createSSEParser((event) => events.push(JSON.parse(JSON.stringify(event))));
    feed(parser);
    parser.end();
    return events;
}

function expectStandard(events) {
    assert.deepEqual(events.map((e) => e.type), ['content', 'content', 'citations', 'done']);
    assert.equal(events.filter((e) => e.type === 'content').map((e) => e.chunk).join(''), 'Observe the natural breath.');
    assert.deepEqual(events[2].citations, [{ title: 'Guide', reference: 'page 3' }]);
}

test('whole buffered stream in one read', () => {
    expectStandard(collect((p) => p.pushText(STREAM)));
});

test('one character per read', () => {
    expectStandard(collect((p) => { for (const ch of STREAM) p.pushText(ch); }));
});

test('one byte per read, including multi-byte UTF-8', () => {
    const text = 'data: {"chunk": "தியானம் 🙏", "type": "content"}\n\ndata: [DONE]\n\n';
    const bytes = new TextEncoder().encode(text);
    const events = collect((p) => { for (const b of bytes) p.pushBytes(Uint8Array.of(b)); });
    assert.equal(events[0].chunk, 'தியானம் 🙏');
    assert.equal(events[1].type, 'done');
});

test('CRLF line endings split across reads', () => {
    const crlf = STREAM.replace(/\n/g, '\r\n');
    expectStandard(collect((p) => { for (let i = 0; i < crlf.length; i += 3) p.pushText(crlf.slice(i, i + 3)); }));
});

test('[DONE] is a completion event, not JSON', () => {
    const events = collect((p) => p.pushText('data: [DONE]\n\n'));
    assert.deepEqual(events, [{ type: 'done' }]);
});

test('error event and malformed data do not throw', () => {
    const events = collect((p) => p.pushText(
        'data: {not json}\n\ndata: {"error": "Sorry", "type": "error", "request_id": "r1"}\n\n'));
    assert.equal(events[0].type, 'parse_error');
    assert.equal(events[1].type, 'error');
    assert.equal(events[1].error, 'Sorry');
});

test('final event without trailing blank line is flushed on end()', () => {
    const events = collect((p) => p.pushText('data: [DONE]'));
    assert.deepEqual(events, [{ type: 'done' }]);
});
