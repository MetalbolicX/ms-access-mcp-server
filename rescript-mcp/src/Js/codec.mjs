// codec.mts — cp1252 / UTF-16LE codec helpers for the TypeScript bridge.
// These replace %raw blocks in ComUi.res and ComDbProps.res that perform
// Buffer codepage conversions unavailable through typed NodeJS bindings.
//
// Node.js Buffer.from/toString do not support cp1252 encoding directly in their
// typed API, so we use TextDecoder/TextEncoder with manual cp1252 byte mapping
// for encoding, and TextDecoder('windows-1252') for decoding.
import { TextDecoder } from "node:util";
// cp1252 is Windows-1252: identical to ISO-8859-1 (Latin1) for 0x00-0x9F,
// but has printable characters in 0x80-0x9F instead of control characters.
// cp1252 decode map: byte value -> Unicode code point
const CP1252_DECODE = [
    "\u0000", "\u0001", "\u0002", "\u0003", "\u0004", "\u0005", "\u0006", "\u0007",
    "\u0008", "\u0009", "\u000A", "\u000B", "\u000C", "\u000D", "\u000E", "\u000F",
    "\u0010", "\u0011", "\u0012", "\u0013", "\u0014", "\u0015", "\u0016", "\u0017",
    "\u0018", "\u0019", "\u001A", "\u001B", "\u001C", "\u001D", "\u001E", "\u001F",
    "\u0020", "\u0021", "\u0022", "\u0023", "\u0024", "\u0025", "\u0026", "\u0027",
    "\u0028", "\u0029", "\u002A", "\u002B", "\u002C", "\u002D", "\u002E", "\u002F",
    "\u0030", "\u0031", "\u0032", "\u0033", "\u0034", "\u0035", "\u0036", "\u0037",
    "\u0038", "\u0039", "\u003A", "\u003B", "\u003C", "\u003D", "\u003E", "\u003F",
    "\u0040", "\u0041", "\u0042", "\u0043", "\u0044", "\u0045", "\u0046", "\u0047",
    "\u0048", "\u0049", "\u004A", "\u004B", "\u004C", "\u004D", "\u004E", "\u004F",
    "\u0050", "\u0051", "\u0052", "\u0053", "\u0054", "\u0055", "\u0056", "\u0057",
    "\u0058", "\u0059", "\u005A", "\u005B", "\u005C", "\u005D", "\u005E", "\u005F",
    "\u0060", "\u0061", "\u0062", "\u0063", "\u0064", "\u0065", "\u0066", "\u0067",
    "\u0068", "\u0069", "\u006A", "\u006B", "\u006C", "\u006D", "\u006E", "\u006F",
    "\u0070", "\u0071", "\u0072", "\u0073", "\u0074", "\u0075", "\u0076", "\u0077",
    "\u0078", "\u0079", "\u007A", "\u007B", "\u007C", "\u007D", "\u007E", "\u007F",
    // 0x80-0x9F: cp1252 specific characters (Euro, smart quotes, etc.)
    "\u20AC", "\uFFFD", "\u201A", "\u0192", "\u201E", "\u2026", "\u2020", "\u2021",
    "\u02C6", "\u2030", "\u0160", "\u2039", "\u0152", "\u017D", "\uFFFD", "\uFFFD",
    "\uFFFD", "\u2018", "\u2019", "\u201C", "\u201D", "\u2022", "\u2013", "\u2014",
    "\u02DC", "\u2122", "\u0161", "\u203A", "\u0153", "\u017E", "\u0178", "\uFFFD",
];
// cp1252 encode map: Unicode code point -> byte value (or -1 if not in cp1252)
const CP1252_ENCODE = new Map([
    [0x20AC, 0x80], [0x201A, 0x82], [0x0192, 0x83], [0x201E, 0x84],
    [0x2026, 0x85], [0x2020, 0x86], [0x2021, 0x87], [0x02C6, 0x88],
    [0x2030, 0x89], [0x0160, 0x8A], [0x2039, 0x8B], [0x0152, 0x8C],
    [0x017D, 0x8E], [0xFFFD, 0x8F], [0xFFFD, 0x90], [0x2018, 0x91],
    [0x2019, 0x92], [0x201C, 0x93], [0x201D, 0x94], [0x2022, 0x95],
    [0x2013, 0x96], [0x2014, 0x97], [0x02DC, 0x98], [0x2122, 0x99],
    [0x0161, 0x9A], [0x203A, 0x9B], [0x0153, 0x9C], [0x017E, 0x9E],
    [0x0178, 0x9F],
    // Additional cp1252 characters
    [0x20AC, 0x80], // Euro sign
]);
/** Encode a string to cp1252 (Windows-1252) byte array.
 *  Mirrors: Array.from(Buffer.from(text, "cp1252")) */
export const encodeCp1252 = (text) => {
    const result = [];
    for (let i = 0; i < text.length; i++) {
        const ch = text.charCodeAt(i);
        if (ch < 0x80) {
            // ASCII: direct byte value
            result.push(ch);
        }
        else if (ch < 0x100) {
            // Latin1 range (0x80-0xFF): same as cp1252 for these
            result.push(ch);
        }
        else {
            // Check cp1252 specific encoding
            const encoded = CP1252_ENCODE.get(ch);
            if (encoded !== undefined) {
                result.push(encoded);
            }
            else {
                // Unknown character: use replacement char or skip
                result.push(0x3F); // '?'
            }
        }
    }
    return result;
};
/** Decode a cp1252 byte array to a string.
 *  Uses TextDecoder which supports windows-1252 encoding directly. */
export const decodeCp1252 = (bytes) => {
    const decoder = new TextDecoder("windows-1252");
    return decoder.decode(Buffer.from(bytes));
};
/** Convert a Buffer to a byte array.
 *  Mirrors: Array.from(buf) */
export const bufferToBytes = (buf) => Array.from(buf);
/** Decode a UTF-16LE byte array, skipping the 2-byte BOM prefix.
 *  Returns empty string if fewer than 2 bytes.
 *  Mirrors: Buffer.from(bytes.slice(2)).toString('utf16le') */
export const decodeUtf16LeSkipBom = (bytes) => {
    if (bytes.length < 2)
        return "";
    return Buffer.from(bytes.slice(2)).toString("utf16le");
};
/** Encode a string to a Buffer using the specified encoding.
 *  Used for SaveAsText temp file writes.
 *  For cp1252, we use manual encoding to handle non-BMP characters. */
export const encodeToBuffer = (text, enc) => {
    if (enc === "windows-1252" || enc === "cp1252") {
        const bytes = encodeCp1252(text);
        return Buffer.from(bytes);
    }
    return Buffer.from(text, enc);
};
/** Encode a string to a byte array using the specified encoding.
 *  Mirrors: Array.from(Buffer.from(textData, enc)) */
export const bytesFromString = (text, enc) => {
    if (enc === "windows-1252" || enc === "cp1252") {
        return encodeCp1252(text);
    }
    return Array.from(Buffer.from(text, enc));
};
/** Decode a byte array to a string using the specified encoding.
 *  Mirrors: Buffer.from(raw).toString(enc) */
export const bytesToString = (raw, enc) => {
    const buf = Buffer.from(raw);
    if (enc === "windows-1252" || enc === "cp1252") {
        return decodeCp1252(raw);
    }
    return buf.toString(enc);
};
