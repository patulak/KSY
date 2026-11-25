"""Analyse the experiment results and write analysis/report.html (open it in a browser).

    python analysis/analyze.py              # uses analysis/results.csv
    python analysis/analyze.py --download   # first downloads the "results" sheet from Google Sheets

Accuracy = share of correct answers, shown with 95 % Wilson intervals.
Reaction time (RT) = median, trials slower than RT_LIMIT_MS are left out of RT statistics only
(the participant was probably distracted).
"""
import argparse
import json
import math
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SHEET_CSV = ("https://docs.google.com/spreadsheets/d/1MOA8RduXDE4ELH2Ej6lBnEAhFyfjtSHaOvPlXZlnjCQ/"
             "export?format=csv&gid=482481306")
PLOTLY_FILE = "plotly-2.35.2.min.js"
PLOTLY_URL = "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"
RT_LIMIT_MS = 10_000
CHANCE = 0.25                     # 4AFC guessing rate
SERIES_OBJECTS = ["pen", "marker", "pencil", "ruler"]
AGE_ORDER = ["<20", "20-29", "30-49", "50+"]
DEVICE_ORDER = ["phone", "tablet", "computer", "other"]


# ---------------------------------------------------------------- helpers
def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def fmt_p(p):
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "n/a"
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


RNG = np.random.default_rng(0)


def median_ci(values, n_boot=2000):
    """95 % bootstrap interval of the median."""
    v = np.asarray(values, float)
    if len(v) < 2:
        return (None, None)
    meds = np.median(RNG.choice(v, size=(n_boot, len(v))), axis=1)
    return (float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5)))


def rt_stats(g):
    """Median RT (+IQR) and median relative RT (+95 % CI) of the RT-valid trials in g."""
    ok = g[g.rt_ok]
    rt, rel = ok.reaction_time_ms, ok.rel
    if rt.empty:
        return {"rt": None, "rt_q1": None, "rt_q3": None, "rel": None, "rel_lo": None, "rel_hi": None}
    lo, hi = median_ci(rel)
    return {"rt": float(rt.median()), "rt_q1": float(rt.quantile(.25)), "rt_q3": float(rt.quantile(.75)),
            "rel": float(rel.median()), "rel_lo": lo, "rel_hi": hi}


def group_stats(df, col, order=None):
    """Accuracy (+CI), median RT, relative RT and counts per level of `col`."""
    levels = order if order else sorted(df[col].dropna().unique(), key=str)
    out = []
    for lv in levels:
        g = df[df[col] == lv]
        if g.empty:
            continue
        k, n = int(g.is_correct.sum()), len(g)
        lo, hi = wilson(k, n)
        out.append({"level": str(lv), "n": n, "correct": k, "acc": k / n, "lo": lo, "hi": hi, **rt_stats(g),
                    "participants": int(g.participant.nunique())})
    return out


def compare_tests(df, col, within=True):
    """Accuracy: Fisher (2 levels) or chi-square on trials.
    RT per person: each participant's median RT per level, then Wilcoxon signed-rank (within-subject factor,
    participants who saw both levels) or Mann-Whitney (between-subject factor, e.g. device).
    These are honest about the small number of people; trial-level tests would overstate the evidence."""
    levels = [lv for lv in df[col].dropna().unique()]
    table = [[int(df[df[col] == lv].is_correct.sum()), int((df[col] == lv).sum() - df[df[col] == lv].is_correct.sum())]
             for lv in levels]
    res = {"acc_p": None, "rt_p": None, "acc_test": "-", "rt_test": "-", "rt_people": 0}
    if len(levels) < 2:
        return res
    if len(levels) == 2:
        res.update(acc_p=stats.fisher_exact(table)[1], acc_test="Fisher exact")
    else:
        try:
            res.update(acc_p=stats.chi2_contingency(table)[1], acc_test="chi-square")
        except ValueError:
            pass
    per = df[df.rt_ok].groupby(["participant", col]).reaction_time_ms.median().unstack()
    if len(levels) == 2 and within:
        both = per.dropna()
        if len(both) >= 3:
            a, b = both.columns[:2]
            res.update(rt_p=stats.wilcoxon(both[a], both[b]).pvalue, rt_people=len(both),
                       rt_test=f"Wilcoxon signed-rank on per-person medians ({len(both)} people)")
    elif len(levels) == 2:
        groups = [per[lv].dropna() for lv in levels]
        if all(len(g) >= 2 for g in groups):
            res.update(rt_p=stats.mannwhitneyu(*groups).pvalue, rt_people=sum(len(g) for g in groups),
                       rt_test=f"Mann-Whitney on per-person medians ({' vs '.join(str(len(g)) for g in groups)} people)")
    return res


def comparison(df, col, title, order=None, labels=None, note="", within=True):
    rows = group_stats(df, col, order)
    if labels:
        for r in rows:
            r["level"] = labels.get(r["level"], r["level"])
    return {"title": title, "rows": rows, "tests": compare_tests(df, col, within), "note": note}


# ---------------------------------------------------------------- load
def load(download):
    csv = HERE / "results.csv"
    if download:
        urllib.request.urlretrieve(SHEET_CSV, csv)
    df = pd.read_csv(csv, dtype={"participant": str, "age_group": str, "device": str, "screen": str})
    df = df.drop_duplicates(["participant", "trial_order"])
    df["is_correct"] = df.is_correct.astype(int)
    df["rt_ok"] = df.reaction_time_ms <= RT_LIMIT_MS
    db = json.loads((ROOT / "renders" / "occlusion_database.json").read_text(encoding="utf-8"))
    meta = pd.DataFrame(db["images"]).set_index("id")
    df["object"] = df.image_id.map(meta.object)
    df["series"] = df.image_id.str.contains(r"_s\d\d$")
    mm = json.loads((HERE / "series_visible_mm.json").read_text())["visible_mm"]
    df["visible_mm"] = df.image_id.map(mm)
    df["step"] = df.image_id.str.extract(r"_s(\d\d)$")[0].astype(float)
    df["n_trials"] = df.groupby("participant").trial_order.transform("max")
    # relative RT: trial RT / that participant's median RT (1.0 = their typical speed)
    person_median = df[df.rt_ok].groupby("participant").reaction_time_ms.median()
    df["rel"] = df.reaction_time_ms / df.participant.map(person_median)
    # image files: the WebP the experiment showed, and the full-resolution render
    df["png"] = df.image_id.map(meta.image_path)
    return df


# ---------------------------------------------------------------- sections
def build(df):
    P = df.drop_duplicates("participant")
    rt_all = df.loc[df.rt_ok, "reaction_time_ms"]
    out = {"overview": {
        "participants": int(df.participant.nunique()), "trials": len(df),
        "accuracy": float(df.is_correct.mean()), "median_rt": float(rt_all.median()),
        "rt_excluded": int((~df.rt_ok).sum()), "rt_limit": RT_LIMIT_MS,
        "first": str(df.timestamp.min())[:10], "last": str(df.timestamp.max())[:10],
        "chance": CHANCE,
    }}

    # demographics (counted per participant)
    def counts(col, order):
        vc = P[col].value_counts()
        levels = [x for x in order if x in vc] + [x for x in vc.index if x not in order]
        return [{"level": lv, "count": int(vc.get(lv, 0))} for lv in (order if col == "age_group" else levels)]
    out["ages"] = counts("age_group", AGE_ORDER)
    out["devices"] = counts("device", DEVICE_ORDER)
    out["languages"] = counts("language", ["cs", "en"])
    per_p = df.groupby("participant").agg(n=("is_correct", "size"), acc=("is_correct", "mean"),
                                          device=("device", "first"), age=("age_group", "first"),
                                          screen=("screen", "first"),
                                          rt=("reaction_time_ms", lambda s: float(s[s <= RT_LIMIT_MS].median())))
    out["participants"] = [{"id": i, **{k: (float(v) if isinstance(v, (np.floating, float)) else (int(v) if isinstance(v, (np.integer,)) else v))
                                        for k, v in r.items()}} for i, r in per_p.sort_values("acc").iterrows()]

    # per image (fixed images and each series object pooled separately)
    img = []
    for image_id, g in df.groupby("image_id"):
        k, n = int(g.is_correct.sum()), len(g)
        lo, hi = wilson(k, n)
        wrong = g.loc[g.is_correct == 0, "chosen_answer"].value_counts()
        img.append({"image": image_id, "object": g.object.iloc[0], "series": bool(g.series.iloc[0]),
                    "occlusion": None if pd.isna(g.occlusion_percentage.iloc[0]) else float(g.occlusion_percentage.iloc[0]),
                    "key": None if pd.isna(g.key_parts_shown.iloc[0]) else int(g.key_parts_shown.iloc[0]),
                    "visible_mm": None if pd.isna(g.visible_mm.iloc[0]) else float(g.visible_mm.iloc[0]),
                    "n": n, "correct": k, "acc": k / n, "lo": lo, "hi": hi, **rt_stats(g),
                    "png": str((ROOT / g.png.iloc[0]).resolve()) if isinstance(g.png.iloc[0], str) else None,
                    "webp": f"../webpage/static/images/{image_id}.webp",
                    "wrong": ", ".join(f"{a} ×{c}" for a, c in wrong.items())})
    out["images"] = img
    out["root"] = str(ROOT.resolve())

    # occlusion / key part - fixed images only (series have no occlusion % yet)
    fixed = df[~df.series].copy()
    fixed["key_shown"] = np.where(fixed.key_parts_shown > 0, "key part visible", "key part hidden")
    out["key"] = comparison(fixed, "key_shown", "Key part visible vs hidden",
                            order=["key part visible", "key part hidden"],
                            note="Fixed images only (the series images have no key-part label yet).")
    # logistic regression of correctness on occlusion % and key part (fixed images)
    out["occ_model"] = logit_occlusion(fixed)
    # matched pairs: same object and occlusion, with / without key
    pairs = []
    for a, b in [("book_marker_10", "book_marker_10_nokey"), ("book_pen_25", "book_pen_25_nokey")]:
        ga, gb = fixed[fixed.image_id == a], fixed[fixed.image_id == b]
        pairs.append({"with": a, "without": b, "acc_with": float(ga.is_correct.mean()), "n_with": len(ga),
                      "acc_without": float(gb.is_correct.mean()), "n_without": len(gb)})
    out["pairs"] = pairs

    out["device"] = comparison(df, "device", "Device", order=DEVICE_ORDER, within=False)
    out["zoom"] = comparison(df, "zoom", "Zoom", order=[1, 2], labels={"1": "1× (whole image)", "2": "2× (zoomed in)"})
    out["mode"] = comparison(df, "answer_mode", "Answer type", order=["text", "image"],
                             labels={"text": "text answers", "image": "image answers"})
    out["age"] = comparison(df, "age_group", "Age group", order=AGE_ORDER, within=False)

    # learning: trial position
    df = df.copy()
    df["bin"] = ((df.trial_order - 1) // 7) * 7 + 1
    learn = []
    for b, g in df.groupby("bin"):
        k, n = int(g.is_correct.sum()), len(g)
        lo, hi = wilson(k, n)
        learn.append({"level": f"{int(b)}–{int(b) + 6}", "start": int(b), "n": n, "acc": k / n, "lo": lo, "hi": hi,
                      **rt_stats(g), "participants": int(g.participant.nunique())})
    ok = df[df.rt_ok]
    rho, rho_p = stats.spearmanr(ok.trial_order, ok.reaction_time_ms)
    # within-participant: RT normalised by each participant's median, so slow people don't dominate
    ok = ok.assign(rel=ok.reaction_time_ms / ok.groupby("participant").reaction_time_ms.transform("median"))
    rho_w, rho_w_p = stats.spearmanr(ok.trial_order, ok.rel)
    first = df[df.trial_order <= df.n_trials / 2].is_correct
    second = df[df.trial_order > df.n_trials / 2].is_correct
    acc_p = stats.fisher_exact([[first.sum(), len(first) - first.sum()], [second.sum(), len(second) - second.sum()]])[1]
    out["learning"] = {"rows": learn, "rho": rho, "rho_p": rho_p, "rho_w": rho_w, "rho_w_p": rho_w_p,
                       "acc_first": float(first.mean()), "errors": int((df.is_correct == 0).sum()),
                       "early_errors": int(((df.is_correct == 0) & (df.trial_order <= 3)).sum()), "acc_second": float(second.mean()), "acc_p": acc_p,
                       "by_block": group_stats(df, "block", [1, 2, 3, 4])}

    out["series"] = series_analysis(df)
    out["rt"] = rt_section(df, fixed)
    return out


def rt_section(df, fixed):
    """Extra reaction-time analyses."""
    ok = df[df.rt_ok]
    res = {}
    # distribution, correct vs wrong
    res["trials"] = [{"rt": int(r.reaction_time_ms), "correct": int(r.is_correct), "image": r.image_id,
                      "pid": r.participant, "trial": int(r.trial_order)} for r in ok.itertuples()]
    df = df.assign(result=np.where(df.is_correct == 1, "correct", "wrong"))
    res["result"] = comparison(df, "result", "Correct vs wrong answers", order=["correct", "wrong"])
    # per person: median + IQR
    res["people"] = []
    for pid, g in ok.groupby("participant"):
        res["people"].append({"id": pid, "device": g.device.iloc[0], "n": len(g), "rt": float(g.reaction_time_ms.median()),
                              "rt_q1": float(g.reaction_time_ms.quantile(.25)), "rt_q3": float(g.reaction_time_ms.quantile(.75)),
                              "acc": float(df[df.participant == pid].is_correct.mean())})
    res["people"].sort(key=lambda p: p["rt"])
    # every condition on the same relative-RT scale
    conds = []

    def add(group, frame, col, order, labels=None):
        for r in group_stats(frame, col, order):
            conds.append({"group": group, **r, "level": (labels or {}).get(r["level"], r["level"])})
    fixed = fixed.assign(key_shown=np.where(fixed.key_parts_shown > 0, "visible", "hidden"))
    add("Key part", fixed, "key_shown", ["visible", "hidden"])
    add("Zoom", df, "zoom", [1, 2], {"1": "1×", "2": "2×"})
    add("Answer type", df, "answer_mode", ["text", "image"])
    add("Device", df, "device", DEVICE_ORDER)
    add("Result", df, "result", ["correct", "wrong"])
    add("Image set", df.assign(set=np.where(df.series, "writing-tool series", "fixed images")), "set",
        ["fixed images", "writing-tool series"])
    df = df.assign(third=pd.cut(df.trial_order / df.n_trials, [0, 1 / 3, 2 / 3, 1], labels=["first third", "middle third", "last third"]).astype(str))
    add("Test position", df, "third", ["first third", "middle third", "last third"])
    res["conditions"] = conds
    # speed-accuracy per image and RT vs occlusion (fixed images)
    res["occ_rho"], res["occ_rho_p"] = [float(x) for x in stats.spearmanr(
        fixed[fixed.rt_ok].occlusion_percentage, fixed[fixed.rt_ok].rel)]
    per_img = df.groupby("image_id").agg(acc=("is_correct", "mean"))
    per_img["rt"] = ok.groupby("image_id").reaction_time_ms.median()
    per_img = per_img.dropna()
    res["sa_rho"], res["sa_rho_p"] = [float(x) for x in stats.spearmanr(per_img.acc, per_img.rt)]
    return res


def logit_occlusion(fixed):
    """Plain logistic regression: correct ~ occlusion % + key part shown (no random effects)."""
    X = np.c_[np.ones(len(fixed)), fixed.occlusion_percentage / 10, (fixed.key_parts_shown > 0).astype(float)]
    y = fixed.is_correct.to_numpy(float)
    beta = np.zeros(3)
    for _ in range(50):                                   # Newton-Raphson
        p = 1 / (1 + np.exp(-X @ beta))
        W = p * (1 - p)
        H = X.T @ (X * W[:, None]) + 1e-9 * np.eye(3)
        step = np.linalg.solve(H, X.T @ (y - p))
        beta += step
        if np.abs(step).max() < 1e-8:
            break
    se = np.sqrt(np.diag(np.linalg.inv(H)))
    z = beta / se
    pv = 2 * stats.norm.sf(np.abs(z))
    names = ["intercept", "occlusion number (+10)", "key part visible"]
    return [{"term": n, "coef": float(b), "or": float(np.exp(b)), "se": float(s), "p": float(q)}
            for n, b, s, q in zip(names, beta, se, pv)]


def series_analysis(df):
    s = df[df.series & df.rt_ok].copy()
    all_s = df[df.series]
    objs = []
    for obj in SERIES_OBJECTS:
        g = s[s.object == obj]
        if g.empty:
            continue
        slope, icpt, r, p, _ = stats.linregress(g.visible_mm, g.reaction_time_ms) if g.visible_mm.nunique() > 1 else (np.nan,) * 5
        steps = (g.groupby(["step", "visible_mm"]).reaction_time_ms.agg(["median", "size"]).reset_index()
                 .rename(columns={"median": "rt", "size": "n"}))
        ga = all_s[all_s.object == obj]
        objs.append({"object": obj, "n": len(ga), "acc": float(ga.is_correct.mean()),
                     "trials": [{"mm": float(m), "rt": float(t), "rel": float(rl), "step": int(st), "pid": pid, "image": im}
                                for m, t, rl, st, pid, im in zip(g.visible_mm, g.reaction_time_ms, g.rel, g.step,
                                                                 g.participant, g.image_id)],
                     "steps": [{k: float(v) for k, v in r.items()} for _, r in steps.iterrows()],
                     "slope": float(slope), "intercept": float(icpt), "p": float(p),
                     "mm_min": float(g.visible_mm.min()), "mm_max": float(g.visible_mm.max())})
    # pooled: log RT ~ visible mm + object (fixed effect) + participant (fixed effect)
    X = pd.get_dummies(s[["object", "participant"]], drop_first=True).astype(float)
    X.insert(0, "mm", s.visible_mm.values)
    X.insert(0, "const", 1.0)
    y = np.log(s.reaction_time_ms.values)
    beta, *_ = np.linalg.lstsq(X.values, y, rcond=None)
    resid = y - X.values @ beta
    dof = len(y) - X.shape[1]
    sigma2 = resid @ resid / dof
    cov = sigma2 * np.linalg.pinv(X.values.T @ X.values)
    b, se = beta[1], math.sqrt(cov[1, 1])
    p = 2 * stats.t.sf(abs(b / se), dof)
    pct_per_10mm = (math.exp(b * 10) - 1) * 100
    ci = [(math.exp((b - 1.96 * se) * 10) - 1) * 100, (math.exp((b + 1.96 * se) * 10) - 1) * 100]
    return {"objects": objs, "n": len(all_s), "acc": float(all_s.is_correct.mean()),
            "pooled": {"pct_per_10mm_visible": pct_per_10mm, "ci": ci, "p": p, "n": len(s), "dof": dof},
            "unit_mm": json.loads((HERE / "series_visible_mm.json").read_text())["unit_mm"]}


# ---------------------------------------------------------------- html
def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if math.isnan(o) else float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true", help="download the latest results from Google Sheets first")
    args = ap.parse_args()
    data = clean(build(load(args.download)))
    data["fmt"] = {k: fmt_p(v) for k, v in [
        ("key_acc", data["key"]["tests"]["acc_p"]), ("key_rt", data["key"]["tests"]["rt_p"]),
        ("dev_acc", data["device"]["tests"]["acc_p"]), ("dev_rt", data["device"]["tests"]["rt_p"]),
        ("zoom_acc", data["zoom"]["tests"]["acc_p"]), ("zoom_rt", data["zoom"]["tests"]["rt_p"]),
        ("mode_acc", data["mode"]["tests"]["acc_p"]), ("mode_rt", data["mode"]["tests"]["rt_p"]),
        ("learn_acc", data["learning"]["acc_p"]), ("learn_rho", data["learning"]["rho_p"]),
        ("learn_rho_w", data["learning"]["rho_w_p"]), ("series", data["series"]["pooled"]["p"]),
        ("result_acc", data["rt"]["result"]["tests"]["acc_p"]), ("result_rt", data["rt"]["result"]["tests"]["rt_p"]),
        ("occ_rho", data["rt"]["occ_rho_p"]), ("sa_rho", data["rt"]["sa_rho_p"])]}
    html = (HERE / "report_template.html").read_text(encoding="utf-8")
    html = html.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False))
    # embed plotly so the report also works offline (downloaded once, cached next to this script)
    plotly = HERE / PLOTLY_FILE
    if not plotly.exists():
        urllib.request.urlretrieve(PLOTLY_URL, plotly)
    tag = f'<script src="{PLOTLY_URL}"></script>'
    html = html.replace(tag, "<script>" + plotly.read_text(encoding="utf-8").replace("</script", "<\\/script") + "</script>")
    (HERE / "report.html").write_text(html, encoding="utf-8")
    print("wrote", HERE / "report.html")


if __name__ == "__main__":
    main()
