// Apify Pinterest Scraper — Main Executable
// Reads config from config.local.mjs (never hardcoded)
//
// Usage:
//   node ~/.workbuddy/skills/apify-pinterest-scraper/scripts/scrape.mjs

import fs from 'fs';
import path from 'path';
import { execFile } from 'child_process';
import { fileURLToPath } from 'url';

// ── Load local config ──────────────────────────────────────────────
const __dir = path.dirname(fileURLToPath(import.meta.url));
let config;
try {
  config = (await import(path.join(__dir, 'config.local.mjs'))).default;
} catch {
  console.error('');
  console.error('  ❌ config.local.mjs not found!');
  console.error('');
  console.error('  Step 1:  Copy the template:');
  console.error(`    cp ${path.join(__dir, 'config.example.mjs')} ${path.join(__dir, 'config.local.mjs')}`);
  console.error('');
  console.error('  Step 2:  Edit config.local.mjs, fill in your Apify API Token.');
  console.error('  Step 3:  Run this script again.');
  console.error('');
  process.exit(1);
}

const { token, baseDir, limit, directions } = config;
if (!token || token === 'apify_api_your_token_here') {
  console.error('  ❌ Please set a valid Apify API Token in config.local.mjs');
  process.exit(1);
}

const API_BASE = 'https://api.apify.com/v2/acts/fatihtahta~pinterest-scraper-search/run-sync-get-dataset-items';

// ── Utilities ──────────────────────────────────────────────────────

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

/** Call Apify API via curl (Node fetch/https timeout on Pinterest CDN) */
function callApify(query) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify({ queries: [query], limit });
    const url = `${API_BASE}?token=${encodeURIComponent(token)}`;
    const args = [
      '-s', '--max-time', '60',
      '-H', 'Content-Type: application/json',
      '-d', data, '-X', 'POST', url,
    ];
    execFile('curl', args, { maxBuffer: 5 * 1024 * 1024 }, (err, stdout) => {
      if (err) return reject(err);
      try { resolve(JSON.parse(stdout)); }
      catch { reject(new Error('JSON parse failed')); }
    });
  });
}

/** Download image via curl (Node fetch/https timeout on Pinterest CDN) */
function downloadImage(url, filepath) {
  return new Promise((resolve, reject) => {
    const args = [
      '-s', '--max-time', '30',
      '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      '-o', filepath, url,
    ];
    execFile('curl', args, { maxBuffer: 5 * 1024 * 1024 }, (err) => {
      if (err) return reject(err);
      try {
        const stat = fs.statSync(filepath);
        if (stat.size === 0) { fs.unlinkSync(filepath); return reject(new Error('empty file')); }
        resolve();
      } catch (e) { reject(e); }
    });
  });
}

/** Extract best available image URL from a pin object */
function getImageUrl(pin) {
  try { return pin.media.images.original.url; } catch {}
  try { return pin.media.images.large.url; } catch {}
  try { return pin.media.images.medium.url; } catch {}
  return null;
}

/** Guess file extension from URL */
function getExt(url) {
  const u = url.toLowerCase();
  if (u.includes('.png'))  return '.png';
  if (u.includes('.jpeg')) return '.jpeg';
  if (u.includes('.webp')) return '.webp';
  return '.jpg';
}

// ── Main ───────────────────────────────────────────────────────────

async function main() {
  // Resolve baseDir: relative to CWD if not absolute
  const outDir = path.isAbsolute(baseDir) ? baseDir : path.resolve(process.cwd(), baseDir);

  console.log('');
  console.log('╔═══════════════════════════════════════════╗');
  console.log('║     Apify Pinterest Batch Scraper         ║');
  console.log(`║     ${String(directions.length).padStart(2)} categories × ${limit} images             ║`);
  console.log(`║     → ${outDir}   ║`);
  console.log('╚═══════════════════════════════════════════╝');
  console.log('');

  ensureDir(outDir);

  // Step 1: parallel API calls
  process.stdout.write('⏳ Fetching API (parallel)…\n');
  const apiPromises = directions.map(d => callApify(d.query));
  const apiResults = await Promise.all(apiPromises);
  process.stdout.write('✅ All API responses received\n\n');

  // Step 2: download per category
  let totalOk = 0;

  for (let idx = 0; idx < directions.length; idx++) {
    const { dir, query } = directions[idx];
    const targetDir = path.join(outDir, dir);
    ensureDir(targetDir);

    const results = apiResults[idx];
    process.stdout.write(`>>> [${dir}]\n`);
    process.stdout.write(`    query: ${query}\n`);

    if (!Array.isArray(results) || results.length === 0) {
      process.stdout.write('    (no results)\n\n');
      continue;
    }

    process.stdout.write(`    API returned ${results.length} items\n`);
    let ok = 0;

    for (let i = 0; i < results.length; i++) {
      const imgUrl = getImageUrl(results[i]);
      if (!imgUrl) {
        process.stdout.write(`    [x] #${i + 1} no image URL\n`);
        continue;
      }

      const ext = getExt(imgUrl);
      const fileId = results[i].id || Date.now().toString(36);
      const fileName = `${i + 1}_${fileId}${ext}`;
      const filePath = path.join(targetDir, fileName);

      try {
        await downloadImage(imgUrl, filePath);
        const sizeB = fs.statSync(filePath).size;
        const sizeStr = sizeB > 1_048_576
          ? (sizeB / 1_048_576).toFixed(1) + 'MB'
          : (sizeB / 1024).toFixed(0) + 'KB';
        process.stdout.write(`    [v] #${i + 1} ${fileName} (${sizeStr})\n`);
        ok++;
        totalOk++;
      } catch (err) {
        process.stdout.write(`    [x] #${i + 1} ${err.message}\n`);
      }
    }

    process.stdout.write(`    ✅ ${ok}/${results.length}\n\n`);
  }

  console.log('╔═══════════════════════════════════════════╗');
  console.log(`║  🎉 Done!  ${String(totalOk).padStart(2)} images saved             ║`);
  console.log(`║  → ${outDir}   ║`);
  console.log('╚═══════════════════════════════════════════╝');
  console.log('');
}

main().catch(err => {
  console.error('❌ Fatal:', err.message);
  process.exit(1);
});
