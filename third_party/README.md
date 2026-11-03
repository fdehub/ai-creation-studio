# Third-party reference and notices

The Muse browser integration in `backend/muse_worker.mjs` uses the DOM selector
and fresh-thread/stream-observation approach documented in the MIT-licensed
[www222fff/muse2api](https://github.com/www222fff/muse2api) project, specifically
`src/muse2api/drivers/browser/dom.py` and `driver.py`, inspected 2026-11-02.

The integration is reimplemented for this application's isolated Playwright
contexts and encrypted account storage. No upstream account pool, extension,
private credentials or complete gateway service is bundled.

The upstream copyright and MIT permission notice are preserved in
`muse2api-LICENSE.txt`. This notice applies to the referenced/adapted portion;
the rest of the project's code is licensed under the MIT License in the root
`LICENSE` file. Preserve both notices when redistributing the adapted code.
