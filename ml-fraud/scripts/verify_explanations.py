"""Check every stated reason in reports/fraud/explanation_cases.csv against the raw facts in the same row."""
import re
import sys
import pandas as pd

path = sys.argv[1] if len(sys.argv) > 1 else "reports/fraud/explanation_cases.csv"
cases = pd.read_csv(path)
FALLBACK = "This transaction is unusual compared with your normal behaviour"

RULES = [  # (regex, test(row, groups) -> bool)
    (r"^The amount is ([\d.]+)x your usual spend in this category$", lambda r, g: abs(r.amount_ratio_cat - float(g[0])) <= 0.06),
    (r"^The amount is ([\d.]+) standard deviations above your normal spending$", lambda r, g: abs(r.amount_z_user - float(g[0])) <= 0.06),
    (r"^This is the first time you have used this device$", lambda r, g: r.is_new_device == 1),
    (r"^This is the first time you have transacted from this city$", lambda r, g: r.is_new_city == 1),
    (r"^This is the first time you have paid this merchant$", lambda r, g: r.is_new_merchant == 1),
    (r"^The payment was made between midnight and 6 AM$", lambda r, g: r.is_night == 1),
    (r"^(\d+) other transactions in the last 10 minutes$", lambda r, g: r.txn_10m == int(g[0])),
    (r"^(\d+) other transactions in the last hour$", lambda r, g: r.txn_1h == int(g[0])),
    (r"^Made in the same second as your previous transaction$", lambda r, g: r.secs_since_last < 1),
    (r"^Only (\d+) seconds since your previous transaction$", lambda r, g: abs(r.secs_since_last - int(g[0])) <= 1),
    (r"^Only (\d+) minutes since your previous transaction$", lambda r, g: abs(r.secs_since_last / 60 - int(g[0])) <= 0.55),
    (r"^Only (\d+)% of your earlier transactions happened at this time of day$", lambda r, g: abs(r.hour_bucket_share * 100 - int(g[0])) <= 1),
    (r"^The amount is (\d+)% of your balance before this payment$", lambda r, g: abs(r.amt_to_prev_balance * 100 - int(g[0])) <= 1),
]

checked = bad = generic = 0
for _, row in cases.iterrows():
    for sentence in str(row.reasons).split(" | "):
        if sentence == FALLBACK:
            generic += 1
            continue
        for pattern, test in RULES:
            m = re.match(pattern, sentence)
            if m:
                checked += 1
                if not test(row, m.groups()):
                    bad += 1
                    print("MISMATCH", row.txn_id, "|", sentence)
                break
        else:
            bad += 1
            print("UNKNOWN SENTENCE", row.txn_id, "|", sentence)
print(f"{len(cases)} cases | {checked} reasons checked against the facts | {bad} mismatches | {generic} generic fallbacks")
