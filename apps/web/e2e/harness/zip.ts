/**
 * Minimal dependency-free ZIP reader for the NI-063 export verification
 * (harness-only code). The NI-058 bundle is a conventional ZIP with a central
 * directory; this reader walks the central directory, inflates each member
 * (stored or deflate) and exposes bytes + CRC32 for the spec's assertions:
 * manifest per-file SHA-256/byte sizes, research.md link resolution and the
 * exact decimal strings in the chart CSV.
 */
import { inflateRawSync } from "node:zlib";

const EOCD_SIGNATURE = 0x06054b50;
const CENTRAL_SIGNATURE = 0x02014b50;
const LOCAL_SIGNATURE = 0x04034b50;

interface ZipMember {
  data: Buffer;
  crc32: number;
}

function findEocd(buffer: Buffer): number {
  // The EOCD is at most 22 bytes + 65535 bytes of comment from the end.
  const minimum = Math.max(0, buffer.length - 22 - 65_536);
  for (let offset = buffer.length - 22; offset >= minimum; offset -= 1) {
    if (buffer.readUInt32LE(offset) === EOCD_SIGNATURE) {
      return offset;
    }
  }
  throw new Error("ZIP end-of-central-directory not found — not a ZIP file?");
}

const crcTable: Uint32Array = (() => {
  const table = new Uint32Array(256);
  for (let index = 0; index < 256; index += 1) {
    let value = index;
    for (let bit = 0; bit < 8; bit += 1) {
      value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
    }
    table[index] = value >>> 0;
  }
  return table;
})();

function crc32(buffer: Buffer): number {
  let crc = 0xffffffff;
  for (let index = 0; index < buffer.length; index += 1) {
    crc = crcTable[(crc ^ buffer[index]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

/**
 * Extract every member of a ZIP archive.
 */
export function readZip(buffer: Buffer): Map<string, ZipMember> {
  const eocd = findEocd(buffer);
  const entries = buffer.readUInt16LE(eocd + 10);
  let offset = buffer.readUInt32LE(eocd + 16);
  const files = new Map<string, ZipMember>();
  for (let index = 0; index < entries; index += 1) {
    if (buffer.readUInt32LE(offset) !== CENTRAL_SIGNATURE) {
      throw new Error(`ZIP central directory corrupted at entry ${index}`);
    }
    const method = buffer.readUInt16LE(offset + 10);
    const expectedCrc = buffer.readUInt32LE(offset + 16);
    const compressedSize = buffer.readUInt32LE(offset + 20);
    const nameLength = buffer.readUInt16LE(offset + 28);
    const extraLength = buffer.readUInt16LE(offset + 30);
    const commentLength = buffer.readUInt16LE(offset + 32);
    const localOffset = buffer.readUInt32LE(offset + 42);
    const name = buffer.subarray(offset + 46, offset + 46 + nameLength).toString("utf-8");
    offset += 46 + nameLength + extraLength + commentLength;

    if (buffer.readUInt32LE(localOffset) !== LOCAL_SIGNATURE) {
      throw new Error(`ZIP local header missing for ${name}`);
    }
    const localNameLength = buffer.readUInt16LE(localOffset + 26);
    const localExtraLength = buffer.readUInt16LE(localOffset + 28);
    const dataStart = localOffset + 30 + localNameLength + localExtraLength;
    const raw = buffer.subarray(dataStart, dataStart + compressedSize);
    const data = method === 0 ? Buffer.from(raw)
      : method === 8 ? inflateRawSync(raw)
        : (() => { throw new Error(`Unsupported ZIP compression method ${method} for ${name}`); })();
    const actualCrc = crc32(data);
    if (actualCrc !== expectedCrc) {
      throw new Error(`ZIP CRC32 mismatch for ${name}: expected ${expectedCrc}, got ${actualCrc}`);
    }
    files.set(name, { data, crc32: actualCrc });
  }
  return files;
}
