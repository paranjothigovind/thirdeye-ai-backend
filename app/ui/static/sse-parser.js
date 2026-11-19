/*
 * Incremental Server-Sent Events parser for the chat stream.
 *
 * - Buffers across network reads, so events split over several chunks
 *   (including multi-byte UTF-8 characters such as Tamil text) parse correctly.
 * - Ignores SSE comments (": keep-alive").
 * - Reports "data: [DONE]" as { type: "done" }.
 * - Reports unparseable data as { type: "parse_error" } instead of throwing.
 *
 * Classic script: defines the global SSEParser (window.SSEParser in browsers);
 * also exports via module.exports when loaded as CommonJS.
 */
(function (root, factory) {
    if (typeof module === 'object' && module && module.exports) {
        module.exports = factory();
    } else {
        root.SSEParser = factory();
    }
})(typeof globalThis !== 'undefined' ? globalThis : self, function () {
    'use strict';

    function createSSEParser(onEvent) {
        let buffer = '';
        const decoder = new TextDecoder('utf-8');

        function dispatch(block) {
            const dataLines = [];
            for (const rawLine of block.split('\n')) {
                const line = rawLine.endsWith('\r') ? rawLine.slice(0, -1) : rawLine;
                if (!line || line.startsWith(':')) continue; // blank or comment
                if (line.startsWith('data:')) {
                    dataLines.push(line.slice(5).replace(/^ /, ''));
                }
            }
            if (dataLines.length === 0) return;
            const data = dataLines.join('\n');
            if (data === '[DONE]') {
                onEvent({ type: 'done' });
                return;
            }
            let parsed;
            try {
                parsed = JSON.parse(data);
            } catch (err) {
                onEvent({ type: 'parse_error', raw: data });
                return;
            }
            onEvent(parsed);
        }

        function pushText(text) {
            // Normalise the whole buffer: a CRLF may be split across two reads
            buffer = (buffer + text).replace(/\r\n/g, '\n');
            let index;
            while ((index = buffer.indexOf('\n\n')) !== -1) {
                const block = buffer.slice(0, index);
                buffer = buffer.slice(index + 2);
                dispatch(block);
            }
        }

        return {
            /** Feed a decoded string chunk. */
            pushText: pushText,
            /** Feed raw bytes from response.body.getReader(). */
            pushBytes: function (bytes) {
                pushText(decoder.decode(bytes, { stream: true }));
            },
            /** Flush at end of stream. */
            end: function () {
                pushText(decoder.decode());
                if (buffer.trim()) dispatch(buffer);
                buffer = '';
            },
        };
    }

    return { createSSEParser: createSSEParser };
});
