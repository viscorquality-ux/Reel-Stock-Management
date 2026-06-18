import streamlit as st
import pandas as pd
import uuid
from sqlalchemy import create_engine, text

st.set_page_config(page_title="Pro Box Planner", layout="wide")

# MySQL Database Connection Setup
# ඔයාගේ Aiven Cloud MySQL URI එක මෙතනට දාලා තියෙන්නේ
DB_URI = 'mysql+pymysql://avnadmin:AVNS_gHRTw4Hzio_XlhXcm7d@mysql-3e9936af-viscorquality-0270.g.aivencloud.com:28643/defaultdb'

# Streamlit වල Database එක හැම තිස්සෙම Connect නොවී එක පාරක් Connect වෙන්න cache කරගන්නවා
@st.cache_resource
def get_db_engine():
    return create_engine(DB_URI)

engine = get_db_engine()

# Constants
REEL_SIZES = list(range(1000, 1501, 50))
TRIM = 10
GAP = 3

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'order_list' not in st.session_state:
    st.session_state.order_list = []

VALID_USERS = {"user1": "123", "user2": "456"}

if not st.session_state.logged_in:
    st.title("🔒 Login to Pro Box Planner")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            if username in VALID_USERS and VALID_USERS[username] == password:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Invalid Username or Password")
    st.stop()

def get_blank_size(l, w, h, flute):
    allowance = {"B": 3.0, "C": 4.0, "E": 1.5, "N": 1.0}.get(flute, 4.0)
    return h + w + (2 * allowance), (2 * l) + (2 * w) + 6

def get_ideal_reels(blank_w):
    results = []
    for reel in REEL_SIZES:
        eff_w = reel - TRIM
        ups = int((eff_w + GAP) // (blank_w + GAP))
        if ups > 0:
            results.append({"Size": reel, "Waste": reel - ((ups * blank_w) + ((ups - 1) * GAP))})
    return sorted(results, key=lambda x: x["Waste"])[:2]

st.title("📦 Professional Corrugated Board Planner")
if st.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

tab1, tab2 = st.tabs(["📝 Order Management", "⚙️ Planning & Combination"])

with tab1:
    st.subheader("Add New Order")
    with st.form("add_order_form"):
        c1, c2, c3, c4 = st.columns(4)
        po_number = c1.text_input("PO Number")
        client_prod = c2.text_input("Client & Product")
        ply = c3.selectbox("Ply", ["3-Ply", "5-Ply", "7-Ply"])
        int_ext = c4.radio("Type", ["INTERNAL", "EXTERNAL"], horizontal=True)
        
        c5, c6, c7, c8 = st.columns(4)
        l = c5.number_input("Length (mm)", value=300.0)
        w = c6.number_input("Width (mm)", value=200.0)
        h = c7.number_input("Height (mm)", value=150.0)
        flute = c8.selectbox("Flute", ["B", "C", "E", "B/C"])
        qty = st.number_input("Quantity", value=1000)
        
        if st.form_submit_button("Save Order"):
            bw, bl = get_blank_size(l, w, h, "C" if flute == "B/C" else flute)
            st.session_state.order_list.append({
                "ID": str(uuid.uuid4())[:8], "PO_Number": po_number, 
                "Client_Product": client_prod, "Blank_W": bw, "Blank_L": bl, "Ply": ply, "Qty": qty
            })
            st.success("Order Added!")
            st.rerun()

    st.subheader("Current Order List")
    for order in list(st.session_state.order_list):
        cols = st.columns([2, 3, 2, 1, 1, 1, 1])
        cols[0].write(order["PO_Number"])
        cols[1].write(order["Client_Product"])
        cols[2].write(f"{order['Blank_W']} x {order['Blank_L']}")
        cols[3].write(order["Ply"])
        cols[4].write(order["Qty"])
        if cols[6].button("Delete", key=f"del_{order['ID']}"):
            st.session_state.order_list = [o for o in st.session_state.order_list if o["ID"] != order["ID"]]
            st.rerun()

with tab2:
    st.subheader("Planning - Select Ideal Reel")
    st.info("ඔබට අවශ්‍ය Option එක මත ක්ලික් කළ විට එය Stock System එක වෙත ඔබව රැගෙන යනු ඇත.")
    
    ph1, ph2, ph3, ph4, ph5 = st.columns([2, 2, 2, 3, 3])
    ph1.write("**PO Number**")
    ph2.write("**Client**")
    ph3.write("**Blank W**")
    ph4.write("**Option 1 (Best)**")
    ph5.write("**Option 2 (Alt)**")
    st.markdown("---")
    
    for order in st.session_state.order_list:
        c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 3, 3])
        c1.write(order["PO_Number"])
        c2.write(order["Client_Product"][:15])
        c3.write(str(order["Blank_W"]))
        
        options = get_ideal_reels(order["Blank_W"])
        base_url = "https://reel-stock-management-new.onrender.com/"
        
        if len(options) > 0:
            opt1 = options[0]
            link1 = f"{base_url}?po={order['PO_Number']}&reel={opt1['Size']}&qty={order['Qty']}"
            c4.link_button(f"Opt 1: {opt1['Size']}mm (W:{opt1['Waste']:.1f})", link1)
            
        if len(options) > 1:
            opt2 = options[1]
            link2 = f"{base_url}?po={order['PO_Number']}&reel={opt2['Size']}&qty={order['Qty']}"
            c5.link_button(f"Opt 2: {opt2['Size']}mm (W:{opt2['Waste']:.1f})", link2)
