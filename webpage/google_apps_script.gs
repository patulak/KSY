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

/** Opening the URL in a browser shows that the deployment works. */
function doGet() {
  return reply({ ok: true, message: "KSY results endpoint is running." });
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
