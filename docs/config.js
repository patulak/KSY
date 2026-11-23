// Deployment settings for the static (GitHub Pages) version.
// Experiment settings (exposure time, answer mode, …) come from app.py via data.json – run
// webpage/build_static.py after changing them.
window.CONFIG = {
  // Web app URL of the Google Apps Script (see webpage/google_apps_script.gs), ends with /exec.
  // Empty = answers are only kept in the browser (and logged to the console) – fine for local testing.
  SHEETS_URL: "https://script.google.com/macros/s/AKfycbyIXgE_bUoHmYd0NFksx2S6DJlQxmtUnDuXMNSqeMxhWNJaV44U5H40dwsWI3oWMuyOmQ/exec",

  // Test panel (red bar). Open the page with ?test=1 to turn it on, ?test=0 to turn it off.
  // Test answers go to the "test" sheet instead of "results". Set to false to disable completely.
  ALLOW_TEST_MODE: true,
};
