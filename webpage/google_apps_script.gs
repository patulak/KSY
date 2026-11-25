/**
 * Google Apps Script that receives answers from the static (GitHub Pages) version (docs/app.js)
 * and appends them to this spreadsheet – one row per answered trial.
 *
 * Setup (once):
 *   1. Create a Google Sheet. Extensions -> Apps Script, replace the code with this file, save.
 *   2. Deploy -> New deployment -> type "Web app":
 *        Execute as: Me,   Who has access: Anyone
 *      Authorize, then copy the Web app URL (ends with /exec) into SHEETS_URL in docs/config.js.
 *   3. After editing this script: Deploy -> Manage deployments -> edit -> Version: New version
 *      (keeps the same URL).
 *
 * Sheets "results" (real participants) and "test" (test mode) are created automatically with the
 * same columns as the Flask CSV files plus "received_at" (server time when the row arrived).
 * File -> Download -> CSV gives the same format as webpage/results/ with that one extra column.
 */

const ID_PATTERN = /^[0-9a-f]{8}$/;
// Stored as plain text, so Sheets doesn't turn e.g. participant "1234e567" into a number or reformat dates.
// ("20-29" would become a date, "390x844" stays text anyway but is listed for clarity.)
const TEXT_COLUMNS = ["participant", "language", "age_group", "device", "screen", "image_id", "options",
                      "correct_answer", "chosen_answer", "answer_mode", "colors", "timestamp", "received_at"];
// "timestamp" = participant's computer clock at the click (can be wrong or in another time zone);
// "received_at" = Google's clock when the row arrived (reliable; later than the click if it was resent).
const TIME_ZONE = "Europe/Prague";

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);   // one request at a time, so simultaneous participants don't overwrite each other
  try {
    const data = JSON.parse(e.postData.contents);
    const columns = Array.isArray(data.columns) ? data.columns.map(String).concat("received_at") : [];
    const rows = Array.isArray(data.rows) ? data.rows.slice(0, 50) : [];
    const receivedAt = Utilities.formatDate(new Date(), TIME_ZONE, "yyyy-MM-dd'T'HH:mm:ss");
    const cache = CacheService.getScriptCache();
    const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    let saved = 0;

    for (const row of rows) {
      if (!row || !ID_PATTERN.test(String(row.participant))) continue;
      // The page resends answers it isn't sure arrived – skip ones already saved (remembered for 6 h).
      const rowId = `${row.test ? "test" : "results"}-${row.participant}-${row.trial_order}`;
      if (cache.get(rowId)) continue;

      const sheet = getSheet(spreadsheet, row.test ? "test" : "results", columns);
      const header = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
      row.received_at = receivedAt;
      const values = header.map((name) => (name in row && row[name] !== null ? row[name] : ""));
      const target = sheet.getRange(sheet.getLastRow() + 1, 1, 1, values.length);
      target.setNumberFormats([header.map((name) => (TEXT_COLUMNS.includes(name) ? "@" : "General"))]);
      target.setValues([values]);
      cache.put(rowId, "1", 21600);
      saved++;
    }
    return reply({ ok: true, saved });
  } catch (error) {
    return reply({ ok: false, error: String(error) });
  } finally {
    lock.releaseLock();
  }
}

/**
 * Opening the URL in a browser shows that the deployment works.
 * ?stats=1 returns anonymous per-participant summaries for the comparison on the end screen:
 *   participants: [[accuracy 0–1, median RT in ms or null, RT standard deviation or null], …] – no IDs.
 *   &sheet=test uses the test sheet, &exclude=<participant> leaves that participant out,
 *   &min=<n> only counts participants with at least n answers (default 10).
 */
function doGet(e) {
  const p = (e && e.parameter) || {};
  if (!p.stats) return reply({ ok: true, message: "KSY results endpoint is running." });
  try {
    const sheetName = p.sheet === "test" ? "test" : "results";
    const minAnswers = Math.max(1, Number(p.min) || 10);
    const summaries = participantSummaries(sheetName);
    const participants = Object.keys(summaries)
      .filter((id) => id !== p.exclude && summaries[id].n >= minAnswers)
      .map((id) => [summaries[id].accuracy, summaries[id].medianRt, summaries[id].sdRt]);
    return reply({ ok: true, participants });
  } catch (error) {
    return reply({ ok: false, error: String(error) });
  }
}

const RT_LIMIT_MS = 10000;   // slower answers are left out of RT (as in analysis/analyze.py)

/** {participant: {n, accuracy, medianRt}} for one sheet, cached for a minute (reading the sheet is slow). */
function participantSummaries(sheetName) {
  const cache = CacheService.getScriptCache();
  const key = `summaries-${sheetName}`;
  const cached = cache.get(key);
  if (cached) return JSON.parse(cached);

  const summaries = {};
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(sheetName);
  if (sheet && sheet.getLastRow() > 1) {
    const [header, ...rows] = sheet.getDataRange().getValues();
    const col = (name) => header.indexOf(name);
    const [iId, iTrial, iCorrect, iRt] = [col("participant"), col("trial_order"), col("is_correct"), col("reaction_time_ms")];
    const groups = {};
    for (const row of rows) {
      const id = String(row[iId]);
      const g = groups[id] || (groups[id] = { trials: {}, rts: [] });
      if (g.trials[row[iTrial]] !== undefined) continue;   // duplicate row
      g.trials[row[iTrial]] = Number(row[iCorrect]) === 1;
      const rt = Number(row[iRt]);
      if (rt > 0 && rt <= RT_LIMIT_MS) g.rts.push(rt);
    }
    for (const id of Object.keys(groups)) {
      const answers = Object.values(groups[id].trials);
      summaries[id] = {
        n: answers.length,
        accuracy: answers.filter(Boolean).length / answers.length,
        medianRt: quantile(groups[id].rts, 0.5),
        sdRt: sampleSd(groups[id].rts),   // sample standard deviation of the answer times
      };
    }
  }
  const json = JSON.stringify(summaries);
  if (json.length < 90000) cache.put(key, json, 60);   // cache values are limited to 100 kB
  return summaries;
}

/** Sample standard deviation (n - 1) – same as sample_sd() in webpage/app.py and sampleSd() in docs/app.js. */
function sampleSd(values) {
  if (values.length < 2) return null;
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  return Math.sqrt(values.reduce((a, v) => a + (v - mean) ** 2, 0) / (values.length - 1));
}

/** Linear interpolation between the sorted values – same as quantile() in webpage/app.py and docs/app.js. */
function quantile(values, p) {
  if (!values.length) return null;
  const v = values.slice().sort((a, b) => a - b);
  const pos = (v.length - 1) * p, i = Math.floor(pos);
  return v[i] + (v[Math.min(i + 1, v.length - 1)] - v[i]) * (pos - i);
}

function getSheet(spreadsheet, name, columns) {
  let sheet = spreadsheet.getSheetByName(name);
  if (sheet) return sheet;
  if (!columns.length) throw new Error("no columns for new sheet");
  sheet = spreadsheet.insertSheet(name);
  sheet.getRange(1, 1, 1, columns.length).setValues([columns]).setFontWeight("bold");
  sheet.setFrozenRows(1);
  return sheet;
}

function reply(object) {
  return ContentService.createTextOutput(JSON.stringify(object)).setMimeType(ContentService.MimeType.JSON);
}
