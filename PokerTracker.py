import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(layout="wide")

# ---------- GLOBAL STYLE ----------
st.markdown("""
<style>
.stApp {
    background-color: #000000;
}

.block-container {
    padding-top: 1rem;
}

h1, h2, h3, h4, h5, h6, label, span, p {
    color: #f5f5f5 !important;
}

.stButton>button {
    background-color: #147a3d;
    color: #f5f5f5;
    border-radius: 6px;
    border: 1px solid #d4af37;
}

.stButton>button:hover {
    background-color: #1c9c4f;
}
</style>
""", unsafe_allow_html=True)

st.title("Boys Poker Sesh")

# ---------- SESSION STATE ----------
if "players" not in st.session_state:
    st.session_state.players = {}

# ---------- LAYOUT ----------
left, right = st.columns([1,2])

# ---------- LEFT SIDE CONTROLS ----------
with left:

    st.header("Players")

    name = st.text_input("Player Name", key="name_input")

    if st.button("Add Player"):
        if name and name not in st.session_state.players and len(st.session_state.players) < 9:
            st.session_state.players[name] = {"buyins": [], "chips": 0}

    st.divider()

    for p in list(st.session_state.players.keys()):

        st.subheader(p)

        buy = st.number_input(
            f"Buy-in {p}",
            min_value=0,
            step=100,
            key=f"buy_{p}"
        )

        c1, c2, c3 = st.columns(3)

        if c1.button("Add Custom", key=f"add_buy_{p}"):
            st.session_state.players[p]["buyins"].append(buy)

        if c2.button("₹1000", key=f"add1000_{p}"):
            st.session_state.players[p]["buyins"].append(1000)

        if c3.button("₹2000", key=f"add2000_{p}"):
            st.session_state.players[p]["buyins"].append(2000)

        for i, b in enumerate(st.session_state.players[p]["buyins"]):
            c1, c2 = st.columns([4,1])
            c1.write(f"₹{b}")
            if c2.button("❌", key=f"del_{p}_{i}"):
                st.session_state.players[p]["buyins"].pop(i)
                st.rerun()

        total = sum(st.session_state.players[p]["buyins"])
        st.write("Total:", total)

        chips = st.number_input(
            f"Final Chips {p}",
            min_value=0,
            step=100,
            key=f"chips_{p}"
        )
        st.session_state.players[p]["chips"] = chips

        st.divider()

    if st.button("Calculate Settlements"):

        profits = {}
        total_buy = 0
        total_chips = 0

        for p, data in st.session_state.players.items():

            buy = sum(data["buyins"])
            chip = data["chips"]

            profits[p] = chip - buy

            total_buy += buy
            total_chips += chip

        imbalance = total_chips - total_buy

        st.subheader("Settlements")

        if imbalance != 0:
            st.write(f"Warning: Chip total and buy-ins differ by ₹{imbalance}")

        winners = [[p, v] for p, v in profits.items() if v > 0]
        losers = [[p, -v] for p, v in profits.items() if v < 0]

        winners.sort(key=lambda x: x[1], reverse=True)
        losers.sort(key=lambda x: x[1], reverse=True)

        i = j = 0

        while i < len(losers) and j < len(winners):

            loser, amount_loser = losers[i]
            winner, amount_winner = winners[j]

            amount = min(amount_loser, amount_winner)

            st.write(f"{loser} pays {winner}: ₹{amount}")

            amount_loser -= amount
            amount_winner -= amount

            if amount_loser == 0:
                i += 1
            else:
                losers[i][1] = amount_loser

            if amount_winner == 0:
                j += 1
            else:
                winners[j][1] = amount_winner

# ---------- RIGHT SIDE TABLE ----------
with right:

    st.header("Table")

    players = list(st.session_state.players.keys())

    seat_positions = [
        ("50%","-5%"),
        ("85%","15%"),
        ("92%","45%"),
        ("85%","75%"),
        ("50%","90%"),
        ("15%","75%"),
        ("8%","45%"),
        ("15%","15%"),
        ("50%","45%")
]

    html = """
<html>
<head>
<style>

body{
margin:0;
padding:0;
background:transparent;
}

.table-container{
width:100%;
display:flex;
justify-content:center;
overflow-x:auto;
}

.poker-table{
position:relative;
width:100%;
max-width:600px;
aspect-ratio:600/350;
background:radial-gradient(circle at center,#147a3d 0%,#0b3b1c 70%,#021107 100%);
border:6px solid #d4af37;
border-radius:200px;
box-shadow:0 0 30px rgba(0,0,0,0.9);
}

.poker-seat{
position:absolute;
width:90px;
height:90px;
border-radius:50%;
background:#111111;
border:2px solid #d4af37;
color:#f5f5f5;
display:flex;
align-items:center;
justify-content:center;
text-align:center;
font-size:12px;
}

/* MOBILE OPTIMIZATION */

@media (max-width:700px){

.poker-seat{
width:55px;
height:55px;
font-size:9px;
}

.poker-table{
max-width:95vw;
}

}

</style>
</head>

<body>

<div class="table-container">
<div class="poker-table">
"""

    for i, (x, y) in enumerate(seat_positions):

        if i < len(players):
            pname = players[i]
            total = sum(st.session_state.players[pname]["buyins"])
            label = f"{pname}<br>₹{total}"
        else:
            label = "Empty"

        html += f"""
        <div class="poker-seat" style="left:{x}; top:{y}; transform: translate(-50%, -50%);"
            {label}
        </div>
        """

    html += """
</div>
</div>
</body>
</html>
"""

    components.html(html, height=420, scrolling=False)
