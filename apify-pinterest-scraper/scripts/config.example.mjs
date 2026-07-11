// Apify Pinterest Scraper — Config Template
// Copy to config.local.mjs and fill in your real token.
// Never commit config.local.mjs.

export default {
  // === REQUIRED: Apify API Token ===
  // Get from https://console.apify.com → Settings → API
  token: 'apify_api_your_token_here',

  // === Output root directory ===
  baseDir: './outputs/pinterest-scraper',

  // === Images per category ===
  limit: 5,

  // === Search categories ===
  // dir:   folder name (Chinese OK)
  // query: Pinterest search keyword (English recommended)
  directions: [
    { dir: '01-示例分类', query: 'example search keyword pinterest' },
  ],
};
