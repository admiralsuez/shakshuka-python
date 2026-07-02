/**
 * Frontend utility for decoding split-encoded content
 * Mirrors backend content_decoder.py functionality
 */

(function() {
    'use strict';

    /**
     * Decode __SHAKSHUKA_SPLIT_B64_V1__ encoded content
     * @param {string} encodedContent - The encoded string
     * @returns {string|null} The decoded content or null if decoding fails
     */
    function decodeSplitB64V1(encodedContent) {
        if (typeof encodedContent !== 'string') {
            return null;
        }

        if (!encodedContent.startsWith('__SHAKSHUKA_SPLIT_B64_V1__')) {
            return null;
        }

        try {
            const b64Payload = encodedContent.substring('__SHAKSHUKA_SPLIT_B64_V1__'.length);
            const decodedStr = atob(b64Payload);
            const parsed = JSON.parse(decodedStr);

            if (typeof parsed === 'object' && parsed !== null) {
                return parsed.primary || '';
            }
            return null;
        } catch (e) {
            console.warn('Failed to decode split-encoded content:', e);
            return null;
        }
    }

    /**
     * Normalize content by decoding any split-encoded strings
     * @param {*} rawContent - The raw content
     * @returns {string} Decoded or original content
     */
    function normalizeContent(rawContent) {
        if (typeof rawContent !== 'string') {
            return String(rawContent || '');
        }

        // Try to decode if it looks like split-encoded content
        if (rawContent.startsWith('__SHAKSHUKA_SPLIT_B64_V1__')) {
            const decoded = decodeSplitB64V1(rawContent);
            if (decoded !== null) {
                return decoded;
            }
            // If decoding fails, return the original
            return rawContent;
        }

        return rawContent;
    }

    // Export to window
    window.ContentDecoder = {
        decodeSplitB64V1,
        normalizeContent
    };
})();
