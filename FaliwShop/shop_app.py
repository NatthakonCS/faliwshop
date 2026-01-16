import streamlit as st
import pandas as pd
import base64
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageOps 
# ลบ qrcode, ImageDraw, ImageFont ออกแล้วครับ
from streamlit_option_menu import option_menu
from streamlit_gsheets import GSheetsConnection

# --- Setup หน้าเว็บ ---
st.set_page_config(page_title="HIGHCLASS", layout="wide")

# --- 🔐 SYSTEM: LOGIN ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

def check_login():
    st.markdown("""
        <style>
            .stTextInput input { text-align: center; }
            div[data-testid="stForm"] { 
                border: 2px solid #FF4B4B; 
                border-radius: 20px; 
                padding: 30px; 
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            }
        </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔐 HIGHCLASS SHOP</h2>", unsafe_allow_html=True)
        with st.form("login_form"):
            user = st.text_input("Username", placeholder="User")
            pwd = st.text_input("Password", type="password", placeholder="Password")
            submitted = st.form_submit_button("LOGIN", use_container_width=True, type="primary")
            
            if submitted:
                # ดึงรหัสลับมาจาก Secrets
                correct_user = st.secrets["credentials"]["username"]
                correct_pass = st.secrets["credentials"]["password"]
                
                if user == correct_user and pwd == correct_pass:
                    st.session_state.logged_in = True
                    st.toast("Welcome back, Boss! 😎")
                    st.rerun()
                else:
                    st.error("❌ Access Denied!")

if not st.session_state.logged_in:
    check_login()
    st.stop()

# --- 👇 ส่วนจัดการ Google Sheets ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1a452nupXAJ_wLEJIE3NOd1bAJTqerphJfqUUhelq1ZY/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CSS ---
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
    footer {visibility: hidden;}
    .stButton>button { border-radius: 12px; font-weight: 600; }
    div[data-testid="stVerticalBlock"] > div[style*="background-color"] {
        border-radius: 16px; border: 1px solid rgba(255,255,255,0.1);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# --- Helper Functions ---
def get_data(worksheet_name):
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet=worksheet_name, ttl=0)
        return df
    except Exception:
        return pd.DataFrame()

def save_data(df, worksheet_name):
    conn.update(spreadsheet=SHEET_URL, worksheet=worksheet_name, data=df)

def image_to_base64(pil_img):
    pil_img = pil_img.convert('RGB')
    pil_img.thumbnail((300, 300))
    buffered = BytesIO()
    pil_img.save(buffered, format="JPEG", quality=80)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/jpeg;base64,{img_str}"

# --- Sidebar ---
with st.sidebar:
    st.markdown("## 🛍️ HIGHCLASS SHOP")
    selected = option_menu(
        menu_title=None,
        options=["Dashboard", "Transactions", "Inventory", "Sold Items"],
        icons=["grid-1x2", "wallet", "box-seam-fill", "bag-check-fill"], 
        default_index=0,
    )

# --- Load Data ---
df_trans = get_data("transactions")
df_prod = get_data("products")

if df_trans.empty:
    df_trans = pd.DataFrame(columns=['date', 'type', 'title', 'amount'])
if df_prod.empty:
    df_prod = pd.DataFrame(columns=['product_id', 'name', 'image_base64', 'sell_price', 'discount_price', 'cost_price', 'status', 'actual_sold_price', 'sold_date'])

# === PAGE: DASHBOARD ===
if selected == "Dashboard":
    st.markdown("### 👋 Overview")
    
    if not df_trans.empty:
        inc = df_trans[df_trans['type']=='รายรับ']['amount'].sum()
        exp = df_trans[df_trans['type']=='รายจ่าย']['amount'].sum()
    else: inc, exp = 0, 0

    if not df_prod.empty:
        sold_items = df_prod[df_prod['status']=='Sold']
        total_revenue = sold_items['actual_sold_price'].sum()
        total_stock_cost = df_prod['cost_price'].sum()
        stock_val = df_prod[df_prod['status']=='Available']['cost_price'].sum()
        profit_clothes = total_revenue - sold_items['cost_price'].sum()
        sold_count = len(sold_items)
    else: 
        total_revenue, total_stock_cost, stock_val, profit_clothes, sold_count = 0, 0, 0, 0, 0

    net_cash = (inc + total_revenue) - (exp + total_stock_cost)

    col1, col2, col3 = st.columns(3)
    col1.metric("✨ Net Profit (Clothes)", f"฿ {profit_clothes:,.0f}", f"{sold_count} items sold")
    col2.metric("💵 Cash Balance", f"฿ {net_cash:,.0f}")
    col3.metric("📦 Stock Value (Asset)", f"฿ {stock_val:,.0f}")

# === PAGE: TRANSACTIONS ===
elif selected == "Transactions":
    st.markdown("### 💸 Income & Expenses")
    with st.form("trans_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([2, 2, 4, 2])
        d_date = c1.date_input("Date", datetime.now())
        d_type = c2.selectbox("Type", ["รายจ่าย", "รายรับ"])
        d_title = c3.text_input("Title")
        d_amt = c4.number_input("Amount", min_value=0.0)
        if st.form_submit_button("Add Entry", type="primary"):
            new_row = pd.DataFrame([{'date': str(d_date), 'type': d_type, 'title': d_title, 'amount': d_amt}])
            updated_df = pd.concat([df_trans, new_row], ignore_index=True)
            save_data(updated_df, "transactions")
            st.toast("Saved!")
            st.rerun()

    if not df_trans.empty:
        st.dataframe(df_trans.
