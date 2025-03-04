import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import plotly.express as px
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from io import BytesIO
from statsmodels.tsa.arima.model import ARIMA
import warnings

# Initial configuration
st.set_page_config(page_title="Inventory System", layout="wide")
st.title("Inventory System - Product Management")

# Files
INVENTORY_FILE = "inventory.csv"
HISTORY_FILE = "change_history.csv"
SALES_FILE = "sales.csv"
USERS = {"admin": "inventory123"}

# Demo data for generic inventory
DEMO_DATA = pd.DataFrame({
    "ID": ["001", "002", "003", "004", "005"],
    "Product": ["Laptop", "T-shirt", "1kg Rice", "Chair", "LED Bulb"],
    "Category": ["Electronics", "Clothing", "Food", "Furniture", "Lighting"],
    "Quantity": [10, 20, 50, 15, 30],
    "Price": [1200.00, 15.50, 2.80, 45.00, 3.75],
    "Supplier": ["Dell", "Zara", "Local", "Ikea", "Philips"],
    "Last Update": ["2025-03-02 10:00:00", "2025-03-01 15:30:00", "2025-02-28 09:15:00", 
                    "2025-03-01 12:00:00", "2025-03-02 14:20:00"],
    "Estimated Demand": [0.0, 0.0, 0.0, 0.0, 0.0]
})

# Demo data for historical sales (30 days)
start_date = datetime(2025, 2, 1)
DEMO_SALES = []
for i in range(30):
    date = start_date + timedelta(days=i)
    DEMO_SALES.extend([
        {"Date": date.strftime("%Y-%m-%d 09:00:00"), "ID": "001", "Product": "Laptop", "Quantity Sold": 1, "Unit Price": 1200.00, "Total": 1200.00, "User": "admin"},
        {"Date": date.strftime("%Y-%m-%d 10:00:00"), "ID": "002", "Product": "T-shirt", "Quantity Sold": 3, "Unit Price": 15.50, "Total": 46.50, "User": "admin"},
        {"Date": date.strftime("%Y-%m-%d 11:00:00"), "ID": "003", "Product": "1kg Rice", "Quantity Sold": 5, "Unit Price": 2.80, "Total": 14.00, "User": "admin"},
        {"Date": date.strftime("%Y-%m-%d 12:00:00"), "ID": "004", "Product": "Chair", "Quantity Sold": 2, "Unit Price": 45.00, "Total": 90.00, "User": "admin"},
        {"Date": date.strftime("%Y-%m-%d 13:00:00"), "ID": "005", "Product": "LED Bulb", "Quantity Sold": 4, "Unit Price": 3.75, "Total": 15.00, "User": "admin"}
    ])
DEMO_SALES = pd.DataFrame(DEMO_SALES)

# Function to load inventory
def load_inventory():
    if not os.path.exists(INVENTORY_FILE):
        DEMO_DATA.to_csv(INVENTORY_FILE, index=False)
        return DEMO_DATA.copy()
    df = pd.read_csv(INVENTORY_FILE)
    df["Price"] = df["Price"].round(2)
    if "Estimated Demand" not in df.columns:
        df["Estimated Demand"] = 0.0
    return df 

# Function to save inventory
def save_inventory(df):
    df["Price"] = df["Price"].round(2)
    df["Estimated Demand"] = df["Estimated Demand"].round(2)
    df.to_csv(INVENTORY_FILE, index=False)

# Function to load sales
def load_sales():
    if not os.path.exists(SALES_FILE):
        DEMO_SALES.to_csv(SALES_FILE, index=False)
        return DEMO_SALES.copy()
    df = pd.read_csv(SALES_FILE)
    df["Unit Price"] = df["Unit Price"].round(2)
    df["Total"] = df["Total"].round(2)
    return df

# Function to save sales
def save_sales(df):
    df["Unit Price"] = df["Unit Price"].round(2)
    df["Total"] = df["Total"].round(2)
    df.to_csv(SALES_FILE, index=False)

# Register changes in history
def register_change(action, product_id, user):
    history = pd.DataFrame({
        "Date": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        "Action": [action],
        "Product ID": [product_id],
        "User": [user]
    })
    if os.path.exists(HISTORY_FILE):
        existing_history = pd.read_csv(HISTORY_FILE)
        history = pd.concat([existing_history, history], ignore_index=True)
    history.to_csv(HISTORY_FILE, index=False)

# Function to calculate estimated demand with ARIMA
def calculate_estimated_demand(sales, inventory, forecast_periods=30):
    sales["Date"] = pd.to_datetime(sales["Date"])
    inventory["Estimated Demand"] = 0.0
    
    for id_prod in inventory["ID"].unique():
        sales_prod = sales[sales["ID"] == id_prod].copy()
        if not sales_prod.empty and len(sales_prod) >= 10:
            daily_sales = sales_prod.groupby(sales_prod["Date"].dt.date)["Quantity Sold"].sum().reset_index()
            daily_sales["Date"] = pd.to_datetime(daily_sales["Date"])
            daily_sales.set_index("Date", inplace=True)
            time_series = daily_sales["Quantity Sold"].resample("D").sum().fillna(0)
            
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    model = ARIMA(time_series, order=(1, 1, 1))
                    result = model.fit()
                    prediction = result.forecast(steps=forecast_periods)
                    estimated_demand = prediction.mean()
                    inventory.loc[inventory["ID"] == id_prod, "Estimated Demand"] = estimated_demand
            except ValueError as e:
                st.warning(f"ARIMA could not be fitted for ID {id_prod}: {str(e)}.")
            except Exception as e:
                st.warning(f"Unexpected error for ID {id_prod}: {str(e)}") 
        else:
            st.info(f"Not enough data for ID {id_prod} (minimum 10 sales).")
    
    return inventory

# Authentication
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.subheader("Log In")
    st.sidebar.markdown("**Demo Credentials:**")   # Added in the sidebar
    st.sidebar.write("User: `admin`")             # Demo credentials
    st.sidebar.write("Password: `inventory123`")  # Demo credentials
    user = st.text_input("User")
    password = st.text_input("Password", type="password")
    if st.button("Log In"):
        if user in USERS and USERS[user] == password:
            st.session_state.authenticated = True
            st.session_state.user = user
            st.success("Session started successfully!")
        else:
            st.error("Incorrect user or password.")
else:
    # Load inventory and sales
    inventory = load_inventory()
    sales = load_sales()

    # Sidebar menu
    menu = st.sidebar.selectbox(
        "Menu",
        ["View Inventory", "Register Sales", "Load Initial Inventory", "Restock", 
         "Search Product", "Edit Product", "Delete Product", "Report", "History"]
    )
    st.sidebar.write(f"User: {st.session_state.user}")
    if st.sidebar.button("Log Out"):
        st.session_state.authenticated = False
        st.session_state.pop("user")
        st.rerun()

    # Option 1: View Inventory
    if menu == "View Inventory":
        st.subheader("Current Inventory")
        if inventory.empty:
            st.warning("The inventory is empty. Please load the initial inventory.")
        else:
            if st.button("Calculate Estimated Demand"):
                inventory = calculate_estimated_demand(sales, inventory)
                save_inventory(inventory)
                st.success("Estimated demand calculated successfully!")

            col1, col2 = st.columns(2)
            with col1:
                category_filter = st.selectbox("Filter by Category", ["All"] + inventory["Category"].unique().tolist())
            with col2:
                supplier_filter = st.selectbox("Filter by Supplier", ["All"] + inventory["Supplier"].unique().tolist())
            
            filtered_inventory = inventory.copy()
            if category_filter != "All":
                filtered_inventory = filtered_inventory[filtered_inventory["Category"] == category_filter]
            if supplier_filter != "All":
                filtered_inventory = filtered_inventory[filtered_inventory["Supplier"] == supplier_filter]
            
            def color_stock(row):
                if row["Quantity"] == 0:
                    return ['background-color: red'] * len(row)
                elif row["Quantity"] < 5:
                    return ['background-color: yellow'] * len(row)
                return [''] * len(row)
            
            st.dataframe(filtered_inventory.style.apply(color_stock, axis=1).format({"Price": "{:.2f}", "Estimated Demand": "{:.2f}"}))
            st.download_button(
                label="Download Inventory as CSV",
                data=filtered_inventory.to_csv(index=False),
                file_name=f"inventory_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

    # Option 2: Register Sales
    elif menu == "Register Sales":
        st.subheader("Register Today's Sales")
        inventory["ID"] = inventory["ID"].astype(str)
        available_products = [f"{row['Product']} (ID: {row['ID']}, Stock: {row['Quantity']})" 
                              for _, row in inventory.iterrows() if row['Quantity'] > 0]
        
        with st.form(key="sales_form"):
            if available_products:
                selected_product = st.selectbox("Select a Product", available_products)
                quantity_sold = st.number_input("Quantity Sold", min_value=1, step=1)
                submit_sale = st.form_submit_button(label="Register Sale")

                if submit_sale:
                    try:
                        sale_id = selected_product.split("ID: ")[1].split(",")[0].strip()
                        if sale_id in inventory["ID"].values:
                            product = inventory[inventory["ID"] == sale_id].iloc[0]
                            if product["Quantity"] >= quantity_sold:
                                inventory.loc[inventory["ID"] == sale_id, "Quantity"] -= quantity_sold
                                inventory.loc[inventory["ID"] == sale_id, "Last Update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                save_inventory(inventory)

                                total_sale = quantity_sold * product["Price"]
                                new_sale = pd.DataFrame({
                                    "Date": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                                    "ID": [sale_id],
                                    "Product": [product["Product"]],
                                    "Quantity Sold": [quantity_sold],
                                    "Unit Price": [product["Price"]],
                                    "Total": [total_sale],
                                    "User": [st.session_state.user]
                                })
                                sales = pd.concat([sales, new_sale], ignore_index=True)
                                save_sales(sales)

                                register_change("Sale", sale_id, st.session_state.user)
                                st.success(f"Sale registered: {quantity_sold} of '{product['Product']}' for ${total_sale:.2f}")
                                inventory = load_inventory()
                            else:
                                st.error(f"Not enough stock. Available: {product['Quantity']}")
                        else:
                            st.error(f"The ID '{sale_id}' was not found in the inventory.")
                    except IndexError:
                        st.error("Error processing the selected product.")
            else:
                st.warning("No products with available stock to sell.")

        st.subheader("Sales Registered Today")
        today = datetime.now().strftime("%Y-%m-%d")
        sales_today = sales[sales["Date"].str.startswith(today)]
        if not sales_today.empty:
            st.dataframe(sales_today.style.format({"Unit Price": "{:.2f}", "Total": "{:.2f}"}))
            daily_total = sales_today["Total"].sum()
            st.write(f"**Today's Total Sales:** ${daily_total:.2f}")
        else:
            st.info("No sales registered for today.")

    # Option 3: Load Initial Inventory
    elif menu == "Load Initial Inventory":
        st.subheader("Load Initial Inventory from CSV")
        st.markdown("""
        **Instructions for the CSV file:**
        - **Required columns (in this order):** `ID`, `Product`, `Category`, `Quantity`, `Price`, `Supplier`, `Last Update`.
        - **Column format:**
          - `ID`: Unique identifier of the product (text, maximum 10 characters).
          - `Product`: Name of the product (text).
          - `Category`: Category of the product (text).
          - `Quantity`: Initial quantity in inventory (integer ≥ 0).
          - `Price`: Unit price of the product (number with up to 2 decimals).
          - `Supplier`: Name of the supplier (text).
          - `Last Update`: Date and time of the last update (format `YYYY-MM-DD HH:MM:SS`).
        - **Separator:** Comma (`,`).
        - **Encoding:** UTF-8.
        - **No index column:** Do not include an additional numeric index column.
        - **Notes:** 
          - All fields are mandatory.
          - IDs must be unique.
          - If the file contains the optional column `Estimated Demand`, it must be a number with up to 2 decimals; otherwise, it will be set to 0.0.
        """)

        uploaded_file = st.file_uploader("Select a CSV file", type=["csv"])
        if uploaded_file is not None:
            try:
                new_inventory = pd.read_csv(uploaded_file)
                required_columns = ["ID", "Product", "Category", "Quantity", "Price", "Supplier", "Last Update"]
                
                if not all(col in new_inventory.columns for col in required_columns):
                    st.error(f"The CSV must contain all required columns: {', '.join(required_columns)}.")
                else:
                    try:
                        new_inventory["Quantity"] = new_inventory["Quantity"].astype(int)
                        new_inventory["Price"] = new_inventory["Price"].astype(float)
                        pd.to_datetime(new_inventory["Last Update"], format="%Y-%m-%d %H:%M:%S")
                    except ValueError as e:
                        st.error(f"Error in data: {str(e)}. Verify that 'Quantity' is an integer, 'Price' is a number, and 'Last Update' is in format `YYYY-MM-DD HH:MM:SS`.")
                    else:
                        if new_inventory["ID"].duplicated().any():
                            st.error("The CSV contains duplicate IDs. Each ID must be unique.")
                        elif new_inventory["Quantity"].lt(0).any():
                            st.error("The 'Quantity' column cannot contain negative values.")
                        elif new_inventory["Price"].lt(0).any():
                            st.error("The 'Price' column cannot contain negative values.")
                        else:
                            new_inventory["Price"] = new_inventory["Price"].round(2)
                            if "Estimated Demand" not in new_inventory.columns:
                                new_inventory["Estimated Demand"] = 0.0
                            else:
                                new_inventory["Estimated Demand"] = new_inventory["Estimated Demand"].fillna(0.0).round(2)
                            
                            st.write("Preview of the initial inventory:")
                            st.dataframe(new_inventory.style.format({"Price": "{:.2f}", "Estimated Demand": "{:.2f}"}))
                            if st.button("Confirm Load"):
                                inventory = new_inventory.copy()
                                save_inventory(inventory)
                                register_change("Load Initial Inventory", "All", st.session_state.user)
                                st.success("Initial inventory loaded successfully!")
                                inventory = load_inventory()
            except pd.errors.EmptyDataError:
                st.error("The CSV file is empty.")
            except pd.errors.ParserError:
                st.error("Error parsing the CSV. Ensure it follows the specified format.")
            except Exception as e:
                st.error(f"Unexpected error processing the file: {str(e)}")

    # Option 4: Restock
    elif menu == "Restock":
        st.subheader("Restock from CSV")
        st.markdown("""
        **Instructions for the CSV file:**
        - **Required columns (in this order):** `ID`, `Product`, `Category`, `Quantity`, `Price`, `Supplier`, `Last Update`.
        - **Column format:**
          - `ID`: Unique identifier of the product (text, maximum 10 characters).
          - `Product`: Name of the product (text).
          - `Category`: Category of the product (text).
          - `Quantity`: Quantity to add to inventory (integer ≥ 1).
          - `Price`: Unit price of the product (number with up to 2 decimals).
          - `Supplier`: Name of the supplier (text).
          - `Last Update`: Date and time of the last update (format `YYYY-MM-DD HH:MM:SS`).
        - **Separator:** Comma (`,`).
        - **Encoding:** UTF-8.
        - **No index column:** Do not include an additional numeric index column.
        - **Notes:** 
          - All fields are mandatory.
          - IDs must be unique and must not already exist in the current inventory.
          - Quantity must be greater than or equal to 1.
          - If the file contains the optional column `Estimated Demand`, it must be a number with up to 2 decimals; otherwise, it will be set to 0.0.
        """)

        uploaded_file = st.file_uploader("Select a CSV file", type=["csv"])
        if uploaded_file is not None:
            try:
                new_products = pd.read_csv(uploaded_file)
                required_columns = ["ID", "Product", "Category", "Quantity", "Price", "Supplier", "Last Update"]
                
                if not all(col in new_products.columns for col in required_columns):
                    st.error(f"The CSV must contain all required columns: {', '.join(required_columns)}.")
                else:
                    try:
                        new_products["Quantity"] = new_products["Quantity"].astype(int)
                        new_products["Price"] = new_products["Price"].astype(float)
                        pd.to_datetime(new_products["Last Update"], format="%Y-%m-%d %H:%M:%S")
                    except ValueError as e:
                        st.error(f"Error in data: {str(e)}. Verify that 'Quantity' is an integer, 'Price' is a number, and 'Last Update' is in format `YYYY-MM-DD HH:MM:SS`.")
                    else:
                        if new_products["ID"].duplicated().any():
                            st.error("The CSV contains duplicate IDs. Each ID must be unique.")
                        elif new_products["ID"].isin(inventory["ID"]).any():
                            st.error("Some IDs in the CSV already exist in the inventory. Use unique IDs for new products.")
                        elif new_products["Quantity"].lt(1).any():
                            st.error("The 'Quantity' column must be greater than or equal to 1 to restock.")
                        elif new_products["Price"].lt(0).any():
                            st.error("The 'Price' column cannot contain negative values.")
                        else:
                            new_products["Price"] = new_products["Price"].round(2)
                            if "Estimated Demand" not in new_products.columns:
                                new_products["Estimated Demand"] = 0.0
                            else:
                                new_products["Estimated Demand"] = new_products["Estimated Demand"].fillna(0.0).round(2)
                            
                            st.write("Preview of products to add:")
                            st.dataframe(new_products.style.format({"Price": "{:.2f}", "Estimated Demand": "{:.2f}"}))
                            if st.button("Confirm Restocking"):
                                inventory = pd.concat([inventory, new_products], ignore_index=True)
                                save_inventory(inventory)
                                for id_prod in new_products["ID"]:
                                    register_change("Restock", id_prod, st.session_state.user)
                                st.success(f"{len(new_products)} product(s) added to inventory successfully!")
                                inventory = load_inventory()
            except pd.errors.EmptyDataError:
                st.error("The CSV file is empty.")
            except pd.errors.ParserError:
                st.error("Error parsing the CSV. Ensure it follows the specified format.")
            except Exception as e:
                st.error(f"Unexpected error processing the file: {str(e)}")

    # Option 5: Search Product
    elif menu == "Search Product":
        st.subheader("Search Product")
        search = st.text_input("Enter ID, Name, or Supplier")
        if search:
            result = inventory[
                inventory["ID"].str.contains(search, case=False, na=False) |
                inventory["Product"].str.contains(search, case=False, na=False) |
                inventory["Supplier"].str.contains(search, case=False, na=False)
            ]
            if not result.empty:
                st.dataframe(result.style.format({"Price": "{:.2f}", "Estimated Demand": "{:.2f}"}))
            else:
                st.warning("No products found with that criteria.")

    # Option 6: Edit Product
    elif menu == "Edit Product":
        st.subheader("Edit Product")
        edit_id = str(st.text_input("Enter the ID of the product to edit"))
        if edit_id and edit_id in inventory["ID"].values:
            product = inventory[inventory["ID"] == edit_id].iloc[0]
            with st.form(key="edit_form"):
                name = st.text_input("Product Name", value=product["Product"])
                category = st.text_input("Category", value=product["Category"])
                quantity = st.number_input("Quantity", min_value=0, step=1, value=int(product["Quantity"]))
                price = st.number_input("Unit Price", min_value=0.0, step=0.01, value=float(product["Price"]), format="%.2f")
                supplier = st.text_input("Supplier", value=product["Supplier"])
                submit_edit = st.form_submit_button(label="Save Changes")

                if submit_edit:
                    inventory.loc[inventory["ID"] == edit_id, ["Product", "Category", "Quantity", "Price", "Supplier", "Last Update"]] = \
                        [name, category, quantity, round(price, 2), supplier, datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                    save_inventory(inventory)
                    register_change("Edit", edit_id, st.session_state.user)
                    st.success(f"Product with ID '{edit_id}' updated successfully!")
                    inventory = load_inventory()
        elif edit_id:
            st.error("ID not found in inventory.")

    # Option 7: Delete Product
    elif menu == "Delete Product":
        st.subheader("Delete Product")
        delete_id = str(st.text_input("Enter the ID of the product to delete"))
        if delete_id and delete_id in inventory["ID"].values:
            product = inventory[inventory["ID"] == delete_id].iloc[0]
            st.write(f"Product to delete: {product['Product']} (Quantity: {product['Quantity']})")
            confirm = st.button("Confirm Deletion")
            if confirm:
                inventory = inventory[inventory["ID"] != delete_id]
                save_inventory(inventory)
                register_change("Delete", delete_id, st.session_state.user)
                st.success(f"Product with ID '{delete_id}' deleted successfully!")
                inventory = load_inventory()
        elif delete_id:
            st.error("ID not found in inventory.")

    # Option 8: Report
    elif menu == "Report":
        st.subheader("Inventory Report")
        if inventory.empty:
            st.warning("No data to generate a report.")
        else:
            total_value = (inventory["Quantity"] * inventory["Price"]).sum()
            low_stock = inventory[inventory["Quantity"] < 5]
            st.write(f"**Total Inventory Value:** ${total_value:.2f}")
            st.write(f"**Products with Low Stock (less than 5 units):** {len(low_stock)}")
            if not low_stock.empty:
                st.dataframe(low_stock.style.format({"Price": "{:.2f}", "Estimated Demand": "{:.2f}"}))
            
            fig = px.bar(inventory.groupby("Category")["Quantity"].sum().reset_index(), 
                        x="Category", y="Quantity", title="Quantity by Category")
            st.plotly_chart(fig) 

            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            elements = []
            title_style = ParagraphStyle(
                name='Title',
                fontSize=14,
                leading=16,
                alignment=1,
                spaceAfter=12
            )
            elements.append(Paragraph("Inventory Report", title_style))
            data = [inventory.columns.tolist()] + inventory.values.tolist()
            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(table)
            doc.build(elements)
            st.download_button(
                label="Download Report as PDF",
                data=buffer.getvalue(),
                file_name=f"report_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf"
            )

    # Option 9: History
    elif menu == "History":
        st.subheader("Change History")
        if os.path.exists(HISTORY_FILE):
            history = pd.read_csv(HISTORY_FILE)
            st.dataframe(history)
        else:
            st.info("No change history recorded yet.")

    # Note at the end
    st.markdown("---")
    st.write(f"Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
