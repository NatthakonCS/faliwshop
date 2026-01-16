import streamlit as st
import pandas as pd
import base64
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageOps, ImageDraw, ImageFont
import qrcode
from streamlit_option_menu import option_menu
from streamlit_gsheets import GSheetsConnection

# --- Setup หน้าเว็บ ---
st.set_page_config(page_title="HIGHCLASS", layout="wide")

# ==========================================
# 🛠️ โซนเครื่องมือ (Helper Functions)
# ==========================================

# 1. ฟังก์ชันสร้าง PromptPay Payload (เขียนเอง ไม่ง้อ Library)
def qrop(account_id, amount):
    target = str(account_id).replace("-", "").replace(" ", "").strip()
    if len(target) == 10 and target.startswith("0"): target = "0066" + target[1:]
    
    data = [
        "000201", "010211",
        f"29370016A000000677010111011300{target}",
        "5802TH", "5303764"
    ]
    if amount:
        amt_str = f"{float(amount):.2f}"
        data.append(f"54{len(amt_str):02}{amt_str}")
    
    raw_data = "".join(data) + "6304"
    crc = 0xFFFF
    for char in raw_data:
        crc ^= ord(char) << 8
        for _ in range(8):
            if (crc & 0x8000): crc = (crc << 1) ^ 0x1021
            else: crc <<= 1
    return raw_data + f"{crc & 0xFFFF:04X}"

# 2. ฟังก์ชันสร้างใบเสร็จ (Receipt Generator)
def create_receipt_image(item_name, price, date_str, shop_name="HIGHCLASS"):
    width, height = 500, 800
    img = Image.new('RGB', (width, height), color='white')
    d = ImageDraw.Draw(img)
    
    # พยายามโหลดฟอนต์ (ถ้าไม่มีใช้ Default)
    try:
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        font_reg = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        font_header = ImageFont.truetype(font_path, 40)
        font_text = ImageFont.truetype(font_reg, 24)
        font_price = ImageFont.truetype(font_path, 50)
        font_small = ImageFont.truetype(font_reg, 18)
    except:
        font_header = font_text = font_price = font_small = ImageFont.load_default()

    def draw_centered(y, text, font, fill="black"):
        bbox = d.textbbox((0, 0), text, font=font)
        x = (width - (bbox[2] - bbox[0])) // 2
        d.text((x, y), text, font=font, fill=fill)

    # วาดข้อความ
    cy = 50
    draw_centered(cy, "RECEIPT", font_header); cy += 60
    draw_centered(cy, shop_name, font_text); cy += 40
    d.line((50, cy, width-50, cy), fill="black", width=3); cy += 40
    d.text((50, cy), f"Date: {date_str}", font=font_text, fill="black"); cy += 50
    d.text((50, cy), f"Item: {item_name}", font=font_text, fill="black"); cy += 80
    draw_centered(cy, "TOTAL AMOUNT", font_text); cy += 50
    draw_centered(cy, f"{price:,.0f} THB", font_price); cy += 80
    d.line((50, cy, width-50, cy), fill="black", width=3); cy += 40

    # สร้าง QR Code
    # 🔴🔴🔴 แก้เบอร์ฟิวตรงนี้ !!! 🔴🔴🔴
    my_promptpay_id = "08xxxxxxxx" 
    
    payload = qrop(my_promptpay_id, price)
    qr = qrcode.QRCode(version=1, box_size=8, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    
    # แปลงเป็น RGB เพื่อกัน Error เวลาแปะ
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    
    qx = (width - qr_img.size[0]) // 2
    img.paste(qr_img, (qx, cy))
    
    draw_centered(height - 60, "Thank You!", font_text)
    return img

# 3. ฟังก์ชันจัดการ Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1a452nupXAJ_wLEJIE3NOd1bAJTqerphJfqUUhelq1ZY/edit?usp=sharing"

def get_data(ws_name):
    try: return conn.read(spreadsheet=SHEET_URL, worksheet=ws_name, ttl=0)
    except: return pd.DataFrame()

def save_data(df, ws_name):
    conn.update(spreadsheet=SHEET_URL, worksheet=ws_name, data=df)

def image_to_base64(pil_img):
    pil_img = pil_img.convert('RGB')
    pil_img.thumbnail((300, 300))
    buffered = BytesIO()
    pil_img.save(buffered, format="JPEG", quality=80)
    return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode()}"

# ==========================================
# 🔐 SYSTEM: LOGIN
# ==========================================
if 'logged_in' not in st.session_state: st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🔐 HIGHCLASS ADMIN</h2>", unsafe_allow_html=True)
    with st.form("login"):
        u = st.text_input("Username"); p = st.text_input("Password", type="password")
        if st.form_submit_button("LOGIN", type="primary"):
            if u == st.secrets["credentials"]["username"] and p == st.secrets["credentials"]["password"]:
                st.session_state.logged_in = True
                st.rerun()
            else: st.error("Wrong Password")
    st.stop()

# ==========================================
# 🛍️ MAIN APP
# ==========================================
df_trans = get_data("transactions")
df_prod = get_data("products")

if df_trans.empty: df_trans = pd.DataFrame(columns=['date', 'type', 'title', 'amount'])
if df_prod.empty: df_prod = pd.DataFrame(columns=['product_id', 'name', 'category', 'image_base64', 'sell_price', 'discount_price', 'cost_price', 'status', 'actual_sold_price', 'sold_date'])

with st.sidebar:
    st.markdown("## 🛍️ HIGHCLASS")
    selected = option_menu(None, ["Dashboard", "Transactions", "Inventory", "Sold Items"], 
                         icons=["grid-1x2", "wallet", "box-seam-fill", "bag-check-fill"], default_index=2)

# --- PAGE: DASHBOARD ---
if selected == "Dashboard":
    st.markdown("### 👋 Overview")
    inc = df_trans[df_trans['type']=='รายรับ']['amount'].sum() if not df_trans.empty else 0
    exp = df_trans[df_trans['type']=='รายจ่าย']['amount'].sum() if not df_trans.empty else 0
    
    rev = df_prod[df_prod['status']=='Sold']['actual_sold_price'].sum() if not df_prod.empty else 0
    cost_all = df_prod['cost_price'].sum() if not df_prod.empty else 0
    stock_val = df_prod[df_prod['status']=='Available']['cost_price'].sum() if not df_prod.empty else 0
    
    sold_items = df_prod[df_prod['status']=='Sold']
    profit = rev - sold_items['cost_price'].sum() if not sold_items.empty else 0
    
    col1, col2, col3 = st.columns(3)
    col1.metric("✨ Net Profit", f"฿ {profit:,.0f}")
    col2.metric("💵 Cash Balance", f"฿ {(inc + rev) - (exp + cost_all):,.0f}")
    col3.metric("📦 Stock Value", f"฿ {stock_val:,.0f}")

# --- PAGE: TRANSACTIONS ---
elif selected == "Transactions":
    st.markdown("### 💸 Income & Expenses")
    with st.form("add_trans", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([2,2,4,2])
        d_date = c1.date_input("Date", datetime.now())
        d_type = c2.selectbox("Type", ["รายจ่าย", "รายรับ"])
        d_title = c3.text_input("Title")
        d_amt = c4.number_input("Amount", min_value=0.0)
        if st.form_submit_button("Add", type="primary"):
            new_row = pd.DataFrame([{'date': str(d_date), 'type': d_type, 'title': d_title, 'amount': d_amt}])
            save_data(pd.concat([df_trans, new_row], ignore_index=True), "transactions")
            st.rerun()
    st.dataframe(df_trans.sort_index(ascending=False), use_container_width=True, hide_index=True)

# --- PAGE: INVENTORY ---
elif selected == "Inventory":
    st.markdown("### 👕 Stock Management")
    
    # โชว์ใบเสร็จ (Modal)
    @st.dialog("🧾 Payment Receipt")
    def show_receipt():
        st.image(st.session_state['last_receipt'], caption="Save This Image", use_container_width=True)
        buf = BytesIO(); st.session_state['last_receipt'].save(buf, format="JPEG")
        st.download_button("⬇️ Download Receipt", buf.getvalue(), st.session_state['last_receipt_name'], "image/jpeg", type="primary")
    
    if 'last_receipt' in st.session_state: show_receipt(); del st.session_state['last_receipt']

    tab_shop, tab_add, tab_hist = st.tabs(["🛍️ Shop", "➕ Add Item", "📊 Log"])
    
    with tab_shop:
        if 'category' not in df_prod.columns: df_prod['category'] = 'Uncategorized'
        all_cats = ["All"] + sorted(df_prod[df_prod['status']=='Available']['category'].astype(str).unique().tolist())
        
        c1, c2 = st.columns([2,1])
        q = c1.text_input("Search", placeholder="Search...", label_visibility="collapsed")
        cat = c2.selectbox("Filter", all_cats, label_visibility="collapsed")
        
        items = df_prod[df_prod['status']=='Available']
        if cat != "All": items = items[items['category']==cat]
        if q: items = items[items['name'].str.contains(q, case=False) | items['product_id'].astype(str).str.contains(q, case=False)]
        
        if items.empty: st.info("No items.")
        
        for i in range(0, len(items), 2):
            cols = st.columns(2)
            for idx, row in enumerate(items.iloc[i:i+2].itertuples()):
                with cols[idx]:
                    with st.container(border=True):
                        if pd.notna(row.image_base64) and str(row.image_base64).startswith('data'):
                            st.image(row.image_base64, use_container_width=True)
                        else: st.markdown("*(No Image)*")
                        
                        st.markdown(f"**{row.name}**")
                        st.caption(f"{row.category} | ID: {row.product_id}")
                        c1, c2 = st.columns(2)
                        c1.markdown(f"🏷️ **{row.sell_price:,.0f}**")
                        c2.markdown(f"📉 <span style='color:red'>{row.discount_price:,.0f}</span>", unsafe_allow_html=True)
                        st.caption(f"Cost: {row.cost_price:,.0f}")
                        
                        ukey = f"{row.product_id}_{row.Index}"
                        with st.popover("⚡ Sell", use_container_width=True):
                            ap = st.number_input("Sold Price", value=float(row.sell_price), key=f"p_{ukey}")
                            if st.button("Confirm", key=f"b_{ukey}", type="primary"):
                                df_prod.loc[row.Index, ['status','actual_sold_price','sold_date']] = ['Sold', ap, str(datetime.now())]
                                save_data(df_prod, "products")
                                
                                # สร้างใบเสร็จ
                                receipt = create_receipt_image(row.name, ap, datetime.now().strftime("%Y-%m-%d %H:%M"))
                                st.session_state['last_receipt'] = receipt
                                st.session_state['last_receipt_name'] = f"Receipt_{row.name}.jpg"
                                st.rerun()

    with tab_add:
        uploaded = st.file_uploader("Image", type=['jpg','png'])
        if uploaded: st.image(uploaded, width=150)
        with st.form("add"):
            c1, c2 = st.columns(2); nid = c1.text_input("ID"); nname = c2.text_input("Name")
            c3, c4 = st.columns(2); ncat = c3.text_input("Category"); ncost = c4.number_input("Cost", min_value=0.0)
            c5, c6 = st.columns(2); nprice = c5.number_input("Sell Price"); nfloor = c6.number_input("Floor Price")
            if st.form_submit_button("Save", type="primary"):
                if nid and nname and uploaded:
                    img = ImageOps.exif_transpose(Image.open(uploaded))
                    new_item = pd.DataFrame([{
                        'product_id': nid, 'name': nname, 'category': ncat if ncat else "General",
                        'image_base64': image_to_base64(img), 'sell_price': nprice, 'discount_price': nfloor,
                        'cost_price': ncost, 'status': 'Available', 'actual_sold_price': 0, 'sold_date': None
                    }])
                    save_data(pd.concat([df_prod, new_item], ignore_index=True), "products")
                    st.success("Added!"); st.rerun()
                else: st.error("Missing info/image")

# --- PAGE: SOLD ITEMS ---
elif selected == "Sold Items":
    st.markdown("### ✅ Sold Out Gallery")
    sold = df_prod[df_prod['status']=='Sold']
    if not sold.empty:
        if 'sold_date' in sold.columns: sold = sold.sort_values(by='sold_date', ascending=False)
        st.metric("Total Sales", f"฿ {sold['actual_sold_price'].sum():,.0f}")
        for i in range(0, len(sold), 2):
            cols = st.columns(2)
            for idx, row in enumerate(sold.iloc[i:i+2].itertuples()):
                with cols[idx]:
                    with st.container(border=True):
                        if pd.notna(row.image_base64): st.image(row.image_base64, use_container_width=True)
                        st.markdown(f"**{row.name}**")
                        c1, c2 = st.columns(2)
                        c1.markdown(f"💰 **{row.actual_sold_price:,.0f}**")
                        prof = row.actual_sold_price - row.cost_price
                        c2.markdown(f"{'🟢' if prof>0 else '🔴'} {prof:,.0f}")
                        
                        with st.popover("❌ Cancel"):
                            if st.button("Restock", key=f"r_{row.Index}"):
                                df_prod.at[row.Index, 'status'] = 'Available'
                                df_prod.at[row.Index, 'actual_sold_price'] = 0
                                df_prod.at[row.Index, 'sold_date'] = None
                                save_data(df_prod, "products")
                                st.rerun()
    else: st.info("No sales yet.")
