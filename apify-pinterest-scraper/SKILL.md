---
name: apify-pinterest-scraper
description: >-
  Batch-scrape Pinterest images via the Apify `fatihtahta/pinterest-scraper-search`
  actor. Define categories + search keywords, then download original-quality
  images into organized folders. Triggers: "Apify抓图", "Pinterest批量",
  "pinterest scrape", "pinterest 采集".
agent_created: true
domain: ["data-collection", "image-scraping", "pinterest"]
---

# Apify Pinterest Scraper

Batch-scrape Pinterest images using Apify's Pinterest Scraper Search actor,
download originals into per-category folders.

## When To Use

- Collecting reference images for a design / mood board
- Gathering digital-human prototype candidates for talking-head videos
- Building an image library for slideshow / content-factory background packs
- Any task described as "抓一批 Pinterest 图", "批量采集 Pinterest", "Apify 抓图"

## Setup

### 1. Get an Apify API Token

1. Register at https://console.apify.com (free plan includes $5 credit)
2. Go to **Settings → API → API Token**, copy it
3. Create the local config file:

```bash
cp ~/.workbuddy/skills/apify-pinterest-scraper/scripts/config.example.mjs \
   ~/.workbuddy/skills/apify-pinterest-scraper/scripts/config.local.mjs
```

4. Edit `config.local.mjs`, fill in your token:

```js
export default {
  token: 'apify_api_your_actual_token_here',
  // ...
};
```

**Never commit `config.local.mjs` to version control.**
**Never paste the token directly into SKILL.md or scrape.mjs.**

### 2. Prerequisites

- Node.js 18+
- curl (installed by default on most systems, not the Node.js wrapper)

## How To Use

### Run the default example

```bash
node ~/.workbuddy/skills/apify-pinterest-scraper/scripts/scrape.mjs
```

### Customize categories and search terms

Edit `config.local.mjs`, modify the `directions` array:

```js
directions: [
  { dir: '01-My Category',  query: 'english search keywords' },
  { dir: '02-Another One',  query: 'different keywords here' },
],
```

- `dir` — folder name for this category (Chinese OK)
- `query` — Pinterest search keyword (English yields richer results)

### Change output directory

Set `baseDir` in `config.local.mjs`:

```js
// 相对路径 → 相对于运行脚本时的 CWD
baseDir: './outputs/my-project',

// 也支持绝对路径
baseDir: 'E:/ai/vedio_factory/outputs/数字人原型筛选',
```

Default: `./outputs/pinterest-scraper` (relative to CWD).

### Change images per category

Set `limit` in `config.local.mjs`.

## How It Works

### Architecture

```
config.local.mjs (token + directions)
        ↓
scrape.mjs reads config
        ↓
【PARALLEL】All API calls fire simultaneously via curl
        ↓
Wait for all responses (Promise.all)
        ↓
【SERIAL】Download images per category
  for each category:
    for each result:
      extract media.images.original.url
      download via curl + User-Agent header
      save as {index}_{pinId}.{ext}
```

### API Details

| Field | Value |
|-------|-------|
| Actor | `fatihtahta/pinterest-scraper-search` |
| Endpoint | `https://api.apify.com/v2/acts/fatihtahta~pinterest-scraper-search/run-sync-get-dataset-items` |
| Method | POST |
| Auth | `?token=<API_TOKEN>` as URL parameter |
| Body | `{"queries":["keyword"], "limit":5}` |

### Response Key Fields

```json
{
  "id": "pin_id",
  "media": {
    "images": {
      "original": { "url": "https://i.pinimg.com/originals/..." },
      "large":    { "url": "https://i.pinimg.com/736x/..." }
    }
  }
}
```

### Known Constraint

**Download must use `curl`, not Node.js `fetch()` / `https.get()`**. 
In the sandboxed environment, Pinterest CDN (`i.pinimg.com`) times out
on Node's native HTTP stack. The system `curl` binary works correctly.

## Files

```
apify-pinterest-scraper/
├── SKILL.md
└── scripts/
    ├── scrape.mjs           ← main executable
    ├── config.example.mjs   ← template config (safe to share)
    └── config.local.mjs     ← your config (DO NOT SHARE)
```

## Token Safety Rules

1. `config.local.mjs` is the **only** place the token lives
2. `scrape.mjs` never contains credentials — it reads from `config.local.mjs`
3. If asked to re-share or show the scrape script, use `config.example.mjs`
   as reference, never expose the real token
