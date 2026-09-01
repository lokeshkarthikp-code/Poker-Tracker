import streamlit as st
import streamlit.components.v1 as components
import json
import os
import uuid
from datetime import datetime

st.set_page_config(layout="wide", page_title="Boys Poker Sesh")

# ============================================================
# CONFIG
# ============================================================

SAVE_FILE = "poker_state.json"          # live game (survives reruns, not redeploys)
SHEET_NAME = "Boys Poker Sesh"          # your Google Sheet name
WORKSHEET = "sessions"                  # tab inside that sheet
MAX_SEATS = 9                           # seats drawn on the felt
CURRENCY = "₹"

SHEET_HEADERS = [
    "session_id", "date", "session_name", "player",
    "buyin_total", "buyin_count", "final_chips", "net",
]

# ============================================================
# STYLE
# ============================================================

st.markdown("""
<style>
.stApp {background-color:#000000;}
.block-container {padding-top:1rem;}
h1,h2,h3,h4,h5,h6,label,span,p {color:#f5f5f5 !important;}
.stButton>button {
  background-color:#147a3d; color:#f5f5f5;
  border-radius:6px; border:1px solid #d4af37;
  padding:0.15rem 0.4rem; font-size:0.8rem;
}
.stButton>button:hover {background-color:#1c9c4f;}
div[data-testid="stVerticalBlockBorderWrapper"] {
  border-color:#2a2a2a !important; border-radius:10px;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# STORAGE LAYER
# Everything the app needs from storage goes through these
# functions. Swapping Sheets for a real database later means
# rewriting this block only.
# ============================================================

def _local_save(players):
    try:
        with open(SAVE_FILE, "w") as f:
            json.dump(players, f)
    except Exception:
        pass


def _local_load():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


@st.cache_resource(show_spinner=False)
def _get_worksheet():
    """Returns (worksheet, error_string). One of the two is always None."""
    try:
        import gspread
        from google.oauth2.credentials import Credentials

        if "gcp_oauth" not in st.secrets:
            return None, "No [gcp_oauth] section found in secrets."

        cfg = st.secrets["gcp_oauth"]
        creds = Credentials(
            token=None,
            refresh_token=cfg["refresh_token"],
            client_id=cfg["client_id"],
            client_secret=cfg["client_secret"],
            token_uri="https://oauth2.googleapis.com/token",
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        client = gspread.authorize(creds)
        book = client.open(SHEET_NAME)

        try:
            ws = book.worksheet(WORKSHEET)
        except Exception:
            ws = book.add_worksheet(title=WORKSHEET, rows=1000, cols=len(SHEET_HEADERS))
            ws.append_row(SHEET_HEADERS)

        if not ws.get_all_values():
            ws.append_row(SHEET_HEADERS)
        return ws, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _ws():
    return _get_worksheet()[0]


def _ws_error():
    return _get_worksheet()[1]


def sheets_ready():
    return _ws() is not None


def save_session_to_sheet(session_name, players):
    """Writes one row per player. Re-saving the same session replaces
    its previous rows instead of appending duplicates.
    Returns (ok, message)."""
    ws = _ws()
    if ws is None:
        return False, "Google Sheets isn't connected. See setup notes."

    session_id = st.session_state.session_id
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []

    for name, data in players.items():
        buyin_total = sum(data["buyins"])
        rows.append([
            session_id, stamp, session_name, name,
            buyin_total, len(data["buyins"]),
            data["chips"], data["chips"] - buyin_total,
        ])

    try:
        # Drop any rows already written for this session, bottom-up so
        # the row indices stay valid as we delete.
        existing = ws.get_all_values()
        stale = [
            i for i, row in enumerate(existing[1:], start=2)
            if row and row[0] == session_id
        ]
        for idx in reversed(stale):
            ws.delete_rows(idx)

        ws.append_rows(rows, value_input_option="USER_ENTERED")
        verb = "Updated" if stale else "Saved"
        return True, f"{verb} {len(rows)} players in the sheet."
    except Exception as e:
        return False, f"Write failed: {e}"


def load_history():
    """Returns a list of dicts, one per player-session. Empty if unavailable."""
    ws = _ws()
    if ws is None:
        return []
    try:
        return ws.get_all_records()
    except Exception:
        return []


def list_sessions():
    """Returns [(session_id, label)] newest first, for the fix-up picker."""
    rows = load_history()
    seen = {}
    for r in rows:
        sid = r.get("session_id")
        if sid and sid not in seen:
            seen[sid] = f"{r.get('session_name') or 'Untitled'} — {r.get('date')}"
    return list(reversed(list(seen.items())))


def delete_session(session_id):
    """Removes every row belonging to one session. Returns (ok, message)."""
    ws = _ws()
    if ws is None:
        return False, "Google Sheets isn't connected."
    try:
        existing = ws.get_all_values()
        stale = [
            i for i, row in enumerate(existing[1:], start=2)
            if row and row[0] == session_id
        ]
        for idx in reversed(stale):
            ws.delete_rows(idx)
        return True, f"Deleted {len(stale)} rows."
    except Exception as e:
        return False, f"Delete failed: {e}"


# ============================================================
# STATE
# ============================================================

if "players" not in st.session_state:
    st.session_state.players = _local_load()

if "session_name" not in st.session_state:
    st.session_state.session_name = datetime.now().strftime("%d %b %Y")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]


def persist():
    _local_save(st.session_state.players)


def add_player(name):
    name = name.strip()
    if not name:
        return "Enter a name first."
    if name in st.session_state.players:
        return f"{name} is already at the table."
    st.session_state.players[name] = {"buyins": [], "chips": 0, "seated": True}
    persist()
    return None


def remove_player(name):
    """Hard delete. Only for players added by mistake."""
    st.session_state.players.pop(name, None)
    persist()


def toggle_seat(name):
    """Frees the seat but keeps buy-ins, chips and settlements intact."""
    d = st.session_state.players[name]
    d["seated"] = not d.get("seated", True)
    persist()


def seated_players():
    return [n for n, d in st.session_state.players.items() if d.get("seated", True)]


def net_of(name):
    d = st.session_state.players[name]
    return d["chips"] - sum(d["buyins"])


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.header("Session")
    st.session_state.session_name = st.text_input(
        "Session name", value=st.session_state.session_name
    )

    if sheets_ready():
        st.success("Sheet connected")
    else:
        st.error("Sheet not connected")
        with st.expander("Why?"):
            st.code(_ws_error() or "Unknown error", language=None)
            st.caption(
                f"Looking for a sheet named exactly: {SHEET_NAME}"
            )
        if st.button("Retry connection", use_container_width=True):
            _get_worksheet.clear()
            st.rerun()

    st.divider()

    if st.button("Save session to sheet", use_container_width=True):
        if not st.session_state.players:
            st.error("No players to save.")
        else:
            ok, msg = save_session_to_sheet(
                st.session_state.session_name, st.session_state.players
            )
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    if st.button("Clear table", use_container_width=True):
        st.session_state.players = {}
        st.session_state.session_id = str(uuid.uuid4())[:8]
        if os.path.exists(SAVE_FILE):
            os.remove(SAVE_FILE)
        st.rerun()

    st.caption("Clearing wipes the current game and starts a new session. "
               "Save to the sheet first.")

    if sheets_ready():
        st.divider()
        with st.expander("Fix a saved session"):
            sessions = list_sessions()
            if not sessions:
                st.caption("Nothing saved yet.")
            else:
                labels = {label: sid for sid, label in sessions}
                pick = st.selectbox("Saved session", list(labels.keys()))
                target = labels[pick]

                st.caption(
                    "Overwrite replaces that session's rows with the table "
                    "you have open right now."
                )

                if st.button("Overwrite with current table",
                             use_container_width=True):
                    if not st.session_state.players:
                        st.error("No players on the table.")
                    else:
                        st.session_state.session_id = target
                        ok, msg = save_session_to_sheet(
                            st.session_state.session_name,
                            st.session_state.players,
                        )
                        _get_worksheet.clear()
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)

                if st.button("Delete this session", use_container_width=True):
                    ok, msg = delete_session(target)
                    _get_worksheet.clear()
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
                    st.rerun()


st.title("Boys Poker Sesh")

tab_game, tab_settle, tab_history = st.tabs(["Table", "Settlements", "History"])


# ============================================================
# TAB 1 — TABLE
# ============================================================

with tab_game:
    add_col, felt_col = st.columns([1, 1.4])

    with add_col:
        c1, c2 = st.columns([3, 1])
        new_name = c1.text_input("Add player", label_visibility="collapsed",
                                 placeholder="Player name")
        if c2.button("Add", use_container_width=True):
            err = add_player(new_name)
            if err:
                st.warning(err)
            else:
                st.rerun()

        seated = seated_players()
        st.caption(f"{len(st.session_state.players)} players · "
                   f"{len(seated)} seated · {MAX_SEATS} seats")

    with felt_col:
        players = seated_players()[:MAX_SEATS]
        seat_positions = [
            (260, -10), (480, 40), (510, 150), (480, 260), (260, 300),
            (40, 260), (10, 150), (40, 40), (260, 150),
        ]

        seats_html = ""
        for i, (x, y) in enumerate(seat_positions):
            if i < len(players):
                p = players[i]
                total = sum(st.session_state.players[p]["buyins"])
                label = f"<b>{p}</b><br>{CURRENCY}{total}"
                style = ""
            else:
                label = "<span style='opacity:.35'>Empty</span>"
                style = "opacity:.5;"
            seats_html += (
                f"<div class='poker-seat' style='left:{x}px;top:{y}px;{style}'>"
                f"{label}</div>"
            )

        components.html(f"""
<html><head><style>
body{{margin:0;padding:0;background:transparent;display:flex;justify-content:center;}}
.scale-wrapper{{transform:scale(0.7);transform-origin:top center;}}
@media (max-width:600px){{.scale-wrapper{{transform:scale(0.5);}}}}
.poker-table{{
position:relative;width:600px;height:350px;margin:10px auto;
background:radial-gradient(circle at center,#147a3d 0%,#0b3b1c 70%,#021107 100%);
border:6px solid #d4af37;border-radius:200px;
box-shadow:0 0 30px rgba(0,0,0,0.9);}}
.poker-seat{{
position:absolute;width:90px;height:90px;border-radius:50%;
background:#111;border:2px solid #d4af37;color:#f5f5f5;
display:flex;align-items:center;justify-content:center;
text-align:center;font-size:12px;line-height:1.35;}}
</style></head><body>
<div class="scale-wrapper"><div class="poker-table">{seats_html}</div></div>
</body></html>""", height=400)

    st.divider()

    if not st.session_state.players:
        st.info("Add players to start tracking buy-ins.")
    else:
        names = list(st.session_state.players.keys())

        # Three players per row keeps the page short instead of one long column.
        for row_start in range(0, len(names), 3):
            cols = st.columns(3)
            for col, p in zip(cols, names[row_start:row_start + 3]):
                with col, st.container(border=True):
                    data = st.session_state.players[p]
                    total = sum(data["buyins"])

                    is_seated = data.get("seated", True)
                    tag = "" if is_seated else "  ·  cashed out"
                    head, seat, kick = st.columns([5, 2, 1])
                    head.markdown(f"**{p}** · {CURRENCY}{total} in{tag}")

                    if seat.button("Sit out" if is_seated else "Sit in",
                                   key=f"seat_{p}",
                                   help="Frees the seat, keeps their money in play"):
                        toggle_seat(p)
                        st.rerun()

                    if kick.button("✕", key=f"kick_{p}", help="Delete player"):
                        if data["buyins"] or data["chips"]:
                            st.session_state[f"warn_{p}"] = True
                        else:
                            remove_player(p)
                            st.rerun()

                    if st.session_state.get(f"warn_{p}"):
                        st.error(
                            f"{p} has money in this game. Use **Sit out** to free "
                            "the seat and keep them in the settlement."
                        )
                        if st.button("Delete anyway", key=f"force_{p}"):
                            st.session_state.pop(f"warn_{p}", None)
                            remove_player(p)
                            st.rerun()

                    b1, b2, b3 = st.columns(3)
                    if b1.button("+2000", key=f"b2k_{p}"):
                        data["buyins"].append(2000); persist(); st.rerun()
                    if b2.button("+5000", key=f"b5k_{p}"):
                        data["buyins"].append(5000); persist(); st.rerun()
                    if b3.button("+10000", key=f"b10k_{p}"):
                        data["buyins"].append(10000); persist(); st.rerun()

                    cc1, cc2 = st.columns([2, 1])
                    custom = cc1.number_input(
                        "Custom", min_value=0, step=100, key=f"cust_{p}",
                        label_visibility="collapsed",
                    )
                    if cc2.button("Add", key=f"addc_{p}") and custom > 0:
                        data["buyins"].append(custom); persist(); st.rerun()

                    if data["buyins"]:
                        st.caption(" · ".join(str(b) for b in data["buyins"]))
                        if st.button("Undo last buy-in", key=f"undo_{p}"):
                            data["buyins"].pop(); persist(); st.rerun()

                    chips = st.number_input(
                        "Final chips", min_value=0, step=100,
                        value=int(data.get("chips", 0)), key=f"chips_{p}",
                    )
                    if chips != data.get("chips"):
                        data["chips"] = chips
                        persist()

                    n = chips - total
                    colour = "#4ade80" if n > 0 else "#f87171" if n < 0 else "#9ca3af"
                    st.markdown(
                        f"<span style='color:{colour} !important;font-weight:600'>"
                        f"Net {CURRENCY}{n:+,}</span>", unsafe_allow_html=True
                    )


# ============================================================
# TAB 2 — SETTLEMENTS
# ============================================================

with tab_settle:
    if not st.session_state.players:
        st.info("No players yet.")
    else:
        profits = {p: net_of(p) for p in st.session_state.players}
        total_buy = sum(sum(d["buyins"]) for d in st.session_state.players.values())
        total_chips = sum(d["chips"] for d in st.session_state.players.values())
        imbalance = total_chips - total_buy

        m1, m2, m3 = st.columns(3)
        m1.metric("Total buy-ins", f"{CURRENCY}{total_buy:,}")
        m2.metric("Chips counted", f"{CURRENCY}{total_chips:,}")
        m3.metric("Imbalance", f"{CURRENCY}{imbalance:+,}")

        if imbalance != 0:
            st.warning(
                f"Chips and buy-ins differ by {CURRENCY}{imbalance:,}. "
                "Recount before settling — someone's final chips are off."
            )

        ranked = sorted(profits.items(), key=lambda kv: kv[1], reverse=True)
        podium = [p for p in ranked if p[1] > 0][:3]
        worst = ranked[-1] if ranked and ranked[-1][1] < 0 else None

        if podium:
            order = [1, 0, 2]          # silver, gold, bronze — left to right
            heights = {0: 130, 1: 95, 2: 70}
            medals = {0: "#d4af37", 1: "#c0c0c0", 2: "#cd7f32"}
            blocks = ""
            for pos in order:
                if pos >= len(podium):
                    continue
                nm, val = podium[pos]
                blocks += f"""
                <div class="col">
                  <div class="name">{nm}</div>
                  <div class="amt">+{CURRENCY}{val:,}</div>
                  <div class="block" style="height:{heights[pos]}px;
                       background:linear-gradient(180deg,{medals[pos]}33,{medals[pos]}11);
                       border-color:{medals[pos]};"></div>
                </div>"""

            loser_html = ""
            if worst:
                loser_html = f"""
                <div class="loser">
                  Biggest loss — <b>{worst[0]}</b> {CURRENCY}{worst[1]:,}
                </div>"""

            components.html(f"""
<html><head><style>
body{{margin:0;background:transparent;font-family:system-ui,sans-serif;color:#f5f5f5;}}
.wrap{{display:flex;justify-content:center;align-items:flex-end;gap:22px;
padding:18px 0 6px;}}
.col{{display:flex;flex-direction:column;align-items:center;width:120px;}}
.name{{font-size:14px;font-weight:600;margin-bottom:2px;}}
.amt{{font-size:12px;color:#4ade80;margin-bottom:6px;}}
.block{{width:100%;border:1px solid;border-radius:6px 6px 0 0;}}
.loser{{text-align:center;font-size:13px;color:#f87171;padding:10px 0 4px;
border-top:1px solid #2a2a2a;margin:0 40px;}}
</style></head><body>
<div class="wrap">{blocks}</div>{loser_html}
</body></html>""", height=250)

        st.subheader("Who pays who")
        winners = [[p, v] for p, v in profits.items() if v > 0]
        losers = [[p, -v] for p, v in profits.items() if v < 0]
        winners.sort(key=lambda x: x[1], reverse=True)
        losers.sort(key=lambda x: x[1], reverse=True)

        if not winners or not losers:
            st.info("Enter final chip counts to calculate settlements.")
        else:
            i = j = 0
            while i < len(losers) and j < len(winners):
                loser, owed = losers[i]
                winner, due = winners[j]
                amount = min(owed, due)
                st.write(f"**{loser}** pays **{winner}** — {CURRENCY}{amount:,}")
                losers[i][1] -= amount
                winners[j][1] -= amount
                if losers[i][1] == 0:
                    i += 1
                if winners[j][1] == 0:
                    j += 1


# ============================================================
# TAB 3 — HISTORY
# ============================================================

with tab_history:
    if not sheets_ready():
        st.info("Connect a Google Sheet to build history across sessions.")
    else:
        rows = load_history()
        if not rows:
            st.info("No saved sessions yet.")
        else:
            stats = {}
            for r in rows:
                name = r.get("player")
                try:
                    net = float(r.get("net") or 0)
                except ValueError:
                    continue
                s = stats.setdefault(
                    name, {"sessions": 0, "wins": 0, "losses": 0,
                           "net": 0.0, "best": 0.0, "worst": 0.0}
                )
                s["sessions"] += 1
                s["net"] += net
                if net > 0:
                    s["wins"] += 1
                elif net < 0:
                    s["losses"] += 1
                s["best"] = max(s["best"], net)
                s["worst"] = min(s["worst"], net)

            table = [
                {
                    "Player": n,
                    "Sessions": s["sessions"],
                    "Up": s["wins"],
                    "Down": s["losses"],
                    "Win rate": f"{s['wins'] / s['sessions']:.0%}",
                    "Lifetime net": round(s["net"]),
                    "Best night": round(s["best"]),
                    "Worst night": round(s["worst"]),
                }
                for n, s in sorted(stats.items(), key=lambda kv: -kv[1]["net"])
            ]

            big_win = max(stats.items(), key=lambda kv: kv[1]["best"])
            big_loss = min(stats.items(), key=lambda kv: kv[1]["worst"])
            top = table[0]
            n_sessions = len({r.get("session_id") for r in rows})

            h1, h2, h3, h4 = st.columns(4)
            h1.metric("Sessions played", n_sessions)
            h2.metric("Biggest single win",
                      f"{CURRENCY}{round(big_win[1]['best']):,}", big_win[0])
            h3.metric("Biggest single loss",
                      f"{CURRENCY}{round(big_loss[1]['worst']):,}", big_loss[0])
            h4.metric("Most up all-time",
                      f"{CURRENCY}{top['Lifetime net']:,}", top["Player"])

            st.divider()
            st.dataframe(table, use_container_width=True, hide_index=True)
            st.bar_chart(
                {r["Player"]: r["Lifetime net"] for r in table},
                color="#d4af37",
            )
            st.caption(f"{len(rows)} player-sessions recorded.")
