# Pre-finalize checklist for Quarto HTML reports

Run through these *before* declaring the report done. Each item is paired with a verification command and a sign-it-passed criterion. Most items have caught a real bug at least once.

## 1. Compile

- [ ] **Render succeeds.** `quarto render <file>.qmd` ends with `Output created: <file>.html`. No tracebacks in the output.
- [ ] **HTML file is non-trivial.** `ls -la <file>.html` shows at least a few hundred KB (a self-contained Quarto HTML with embed-resources is typically 1–2 MB).

## 2. Visual inspection (mandatory)

Do not infer visual quality from the `.qmd` source. Render to a screenshot and read it.

- [ ] **Take a tall full-page screenshot** with the bundled Chromium:

  ```bash
  CHROME=$(ls -1 ~/.cache/puppeteer/chrome/linux-*/chrome-linux*/chrome 2>/dev/null | head -1)
  "$CHROME" --headless=new --disable-gpu --no-sandbox \
    --password-store=basic --use-mock-keychain \
    --user-data-dir=/tmp/chrome-headless-quarto \
    --window-size=1800,8000 --virtual-time-budget=4000 \
    --screenshot=/tmp/report_shot.png "file://$PWD/<file>.html"
  ```

  The `--password-store=basic`, `--use-mock-keychain`, and isolated `--user-data-dir` flags keep headless Chrome away from libsecret / GNOME keyring. Without them the first launch on a Linux desktop pops a "create a keyring password" dialog that blocks the screenshot and prompts the user with a request unrelated to the task. The flags are safe in headless mode (no real credentials are being stored).

- [ ] **Crop into readable slices** with PIL (Pillow available in any modern python env):

  ```python
  from PIL import Image
  img = Image.open('/tmp/report_shot.png')
  W, H = img.size
  for k, top in enumerate(range(0, H, 1400)):
      crop = img.crop((0, top, W, min(top+1400, H))).resize((W//2, (min(top+1400,H)-top)//2))
      crop.save(f'/tmp/slice_{k:02d}.png')
  ```

- [ ] **Read each slice** with the multimodal Read tool. Verify visual quality directly.

## 3. Tables

- [ ] **Wide tables show a horizontal scrollbar inside their `.gt-scroll` container.** Especially comparison tables with spanners. Open the HTML in a browser and confirm.

- [ ] **Long tables show a vertical scrollbar with a sticky `<thead>`.** To verify sticky behavior in a screenshot, temporarily inject a scroll-on-load shim:

  ```html
  <script>
  window.addEventListener('load', () => setTimeout(() =>
    document.querySelectorAll('.gt-scroll').forEach(d => { d.scrollTop = 220; }), 100));
  </script>
  ```

  Re-render, take a screenshot, and confirm the column-label row (and spanner row, if present) is pinned at the top of each container with the scrolled body below. Remove the shim after verifying.

- [ ] **Narrow tables fill the page width** rather than appearing as a thin band. The `width: 100%; min-width: max-content` rule handles this; if a table is narrower than expected, check whether the rule was overridden somewhere.

- [ ] **First column is the row identifier** (variable name, ticker, observation ID), not a category or grouping column. When a sticky-left-column rule is in use, the first column is what stays visible during horizontal scroll, so it must carry the row label. Categories that would naturally sit in the first column belong in row groups instead.

- [ ] **No category column repeats the same value across consecutive rows.** Convert any such column into a row group via `gt.GT(..., groupname_col="...")` or `tab_row_group_*`. Acceptable fallback: blank out repeats so only the first row of each run shows the value. Either is fine; never leave the raw repetition.

- [ ] **Spanner alignment is correct.** In tables built with `tab_spanner`, the rowspan=2 columns (un-spanned columns like ID, label, name) align with the spanner row at the same vertical position — *not* offset by 26px. The `:not([rowspan])` selector should handle this; if it's broken, check whether the selector survived editing.

- [ ] **Row-group banners stay pinned at left:0 during horizontal scroll, so the section label remains visible.**

- [ ] **Dates render as YYYY-MM-DD** (not `m_day_year` or any local format). Spot-check a few date cells.

- [ ] **Verbose category names are shortened** where appropriate. Check the `DISPLAY_NAME_OVERRIDES` dict captures the published shorthand from the source paper.

## 4. Print output

- [ ] **`print()` lines wrap rather than show a horizontal scrollbar.** Especially long narrative lines like "This replication identifies N episodes between ... and ...".
- [ ] **Fixed-width table-aligned prints fit the page width without scrolling.** If they don't, convert to a `great_tables` table — wrapping table-aligned text would break the alignment.

## 5. Diagnostic helpers (when something looks off)

When the visual doesn't match what the CSS says it should:

- [ ] **Add a temporary lime border** to `.gt-scroll`:
  ```css
  .gt-scroll { border: 4px solid lime !important; background: #fffaef !important; }
  ```
  Re-render. If the border doesn't show, the CSS class isn't matching — there's a parsing error or the wrapper isn't being applied. If the border does show but the layout is still wrong, the issue is with specific properties, not class matching.

- [ ] **Inspect the rendered DOM** with regex to confirm the actual HTML structure matches assumptions:
  ```python
  import re
  with open('file.html') as f: s = f.read()
  for m in re.finditer(r'<th[^>]+rowspan="2"[^>]*>', s):
      print(s[m.start():m.end()+50])
  ```
  This is how the rowspan=2 trap was originally diagnosed.

- [ ] **Inspect great_tables' inner div inline styles.** They include `overflow-x:auto; overflow-y:auto; height:auto`, which is the most common reason sticky thead silently fails:
  ```python
  import re
  with open('file.html') as f: s = f.read()
  m = re.search(r'<div class="gt-scroll".*?<div id="[^"]+" style="([^"]+)"', s)
  if m: print(m.group(1))
  ```
  If you see overflow:auto on the inner div without the `.gt-scroll > div { overflow: visible !important }` override winning, the override is missing or being beaten by another rule.

## 6. Cleanup

- [ ] **Diagnostic styles removed.** No `border: 4px solid lime`, no `background: red`, no `/* DIAGNOSTIC */` comments.
- [ ] **Diagnostic scripts removed.** No `<script>` block scrolling `.gt-scroll` on load.
- [ ] **Final `max-height` is reasonable.** `560px` is the default; adjust per-table only when content warrants it.
- [ ] **Code-folded chunks have `#| echo: false` or `#| include: false`** as appropriate. Setup chunks should be fully hidden (`include: false`); content-producing chunks should hide the code but keep the output (`echo: false`).

## 7. Honesty about output

- [ ] **If you couldn't compile or screenshot, say so.** The user's CLAUDE.md is explicit: "If you cannot test a visual or compiled output, say so explicitly rather than claiming success." Don't claim "the report renders correctly" without evidence.
