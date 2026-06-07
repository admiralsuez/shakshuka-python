/**
 * Timestamp Formatter
 * Converts ISO 8601 timestamps to human-readable format
 * E.g., "2026-05-24T19:22:01Z" → "24th May 2026 at 7:22 pm"
 */

const TimestampFormatter = {
    /**
     * Get the ordinal suffix for a day number (1st, 2nd, 3rd, 4th, etc.)
     */
    getOrdinalSuffix(day) {
        if (day > 3 && day < 21) return 'th';
        switch (day % 10) {
            case 1: return 'st';
            case 2: return 'nd';
            case 3: return 'rd';
            default: return 'th';
        }
    },

    /**
     * Format ISO timestamp to human-readable format
     * Input: "2026-05-24T19:22:01Z" or "2026-05-24T19:22:01"
     * Output: "24th May 2026 at 7:22 pm"
     */
    formatISO(isoString) {
        if (!isoString) return '';
        try {
            const date = new Date(isoString);
            const day = date.getDate();
            const month = date.toLocaleString('en-US', { month: 'long' });
            const year = date.getFullYear();
            
            let hours = date.getHours();
            const minutes = String(date.getMinutes()).padStart(2, '0');
            const ampm = hours >= 12 ? 'pm' : 'am';
            
            // Convert to 12-hour format
            if (hours > 12) {
                hours -= 12;
            } else if (hours === 0) {
                hours = 12;
            }
            
            const ordinal = this.getOrdinalSuffix(day);
            return `${day}${ordinal} ${month} ${year} at ${hours}:${minutes} ${ampm}`;
        } catch (e) {
            return String(isoString);
        }
    },

    /**
     * Format timestamp (alias for formatISO)
     */
    format(timestamp) {
        return this.formatISO(timestamp);
    }
};

// Export globally
window.TimestampFormatter = TimestampFormatter;
