import fitz  # PyMuPDF
from PIL import Image
import os, sys
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
import pandas as pd
import numpy as np
import cv2
import re
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

#pdf_path = sys.argv[1]
images = "images"
output_folder = "output"
#lim = int(sys.argv[2])

# Azure API and Endpoint keys
key = os.environ['AZURE_KEY1']
endpoint = os.environ['AZURE_ENDPOINT']

# Razorpay credentials
razorpay_key_id = os.environ['RAZORPAY_KEY_ID']
razorpay_key_secret = os.environ['RAZORPAY_KEY_SECRET']

os.system(f"rm -rf {images}")
os.system(f"mkdir {images}")

os.system(f"rm -rf {output_folder}")
os.system(f"mkdir {output_folder}")

def create_razorpay_order(amount, currency='INR'):
    client = razorpay.Client(auth=(razorpay_key_id, razorpay_key_secret))
    order_data = {
        'amount': amount,
        'currency': currency,
        'payment_capture': 1  # Auto capture payments
    }
    order = client.order.create(data=order_data)
    return order

    
def pdf_to_png(pdf_path, output_folder, dpi, lim):
    pdf_document = fitz.open(pdf_path)

    for page_number in range(0,lim):
        page = pdf_document.load_page(page_number)

        # Set the zoom factor to achieve the desired DPI
        zoom_factor = dpi / 72.0
        mat = fitz.Matrix(zoom_factor, zoom_factor)
        pixmap = page.get_pixmap(matrix=mat)

        image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)

        image.save(f"{output_folder}/page_{page_number + 1}.png")

    pdf_document.close()

# Function to analyze layout of the document
def analyze_layout(local_file_path):
    # Initializing the Document Analysis Client with endpoint and key
    document_analysis_client = DocumentAnalysisClient(
        endpoint=endpoint, credential=AzureKeyCredential(key)
    )

    # Opening the file and analyzing the layout
    with open(local_file_path, "rb") as f:
        poller = document_analysis_client.begin_analyze_document(
            "prebuilt-layout", document=f
        )
        result = poller.result()
    return result

# Function to extract table data from the result
def extract_table_data(result):
    tables = []
    for table in result.tables:
        rows = []
        for cell in table.cells:
            while len(rows) <= cell.row_index:
                rows.append([])
            rows[cell.row_index].append(cell.content)
        tables.append(rows)
    return tables

# Convert the extracted tables into pandas dataframes
def tables_to_dataframes(tables):
    dataframes = [pd.DataFrame(table) for table in tables]
    print("Number of dfs is {}".format(len(dataframes)))
    return dataframes

# Function to save the tables in CSV and Excel format
def save_tables(dataframes, base_filename, output_folder):
    for i, df in enumerate(dataframes):
        #csv_filename = f"{output_folder}/{base_filename}_table_{i}.csv"
        xlsx_filename = f"{output_folder}/{base_filename}_table_{i}.xlsx"
        #df.to_csv(csv_filename, index=False)
        df.to_excel(xlsx_filename, index=False)

def is_valid_filename(filename, lim):
    # Check if the filename ends with the specified extensions
    if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.pdf')):
        # Use a regular expression to match the _{number} pattern
        match = re.search(r'_(\d+)\.png$', filename.lower())
        if match:
            # Extract the number and check if it is less than 4
            number = int(match.group(1))
            if number <= lim:
                return True
    return False

def createCombinedXls(folder_path, output_file):
    # List all files in the directory
    all_files = os.listdir(folder_path)

    # Filter out the relevant Excel files
    excel_files = [file for file in all_files if file.startswith('page_') and file.endswith('_table_0.xlsx')]

    # Sort the files to ensure they are in the correct order
    excel_files.sort()

    # Create a Pandas ExcelWriter object
    with pd.ExcelWriter(output_file) as writer:
        for i, file_name in enumerate(excel_files, start=1):  # Enumerate starts at 1 for sheet naming
            file_path = os.path.join(folder_path, file_name)

            # Read the Excel file
            df = pd.read_excel(file_path)

            # Write the DataFrame to a new sheet in the output file
            df.to_excel(writer, sheet_name=f'sheet_{i}', index=False)

    print(f'Combined sheet have been saved to {output_file}')


def createXls(directory_path, output_folder, lim):
    # Loop through each file in the directory
    for filename in os.listdir(directory_path):
        if is_valid_filename(filename, lim):
                file_path = os.path.join(directory_path, filename)
                print(f"Analyzing {filename}...")

                result = analyze_layout(file_path)

                tables = extract_table_data(result)
                dataframes = tables_to_dataframes(tables)
                save_tables(dataframes, os.path.splitext(filename)[0], output_folder)

                print(f"Completed analysis for {filename}. Generating output files...")


def main():
    st.title("✨ Transform Your Bank Statement into Excel with AI! 📊")
    st.markdown("<h3 style='font-size: 20px;'>Are you looking to effortlessly extract your transactions from a PDF bank statement into an Excel spreadsheet? With the power of AI, this process is now simpler and faster than ever! 🚀</h3>", unsafe_allow_html=True)
    st.markdown("<h4 style='font-size: 15px;'>Get the first 2 pages of your PDF absolutely free! After that, it's just Rs 2 per additional page.</h4>", unsafe_allow_html=True)

    pdf_file = st.file_uploader("Upload your Bank Statement PDF file", type="pdf")
    lim = st.number_input("Enter the end page for extraction", min_value=1, value=1)

    st.markdown("<h3 style='font-size: 15px;'>Click on Start to extract transactions to Excel</h3>", unsafe_allow_html=True)
    start_button = st.button("Start")

    if start_button:
        if pdf_file is not None and lim is not None:
            with open("temp.pdf", "wb") as f:
                f.write(pdf_file.getbuffer())

            images_folder = "images"
            output_folder = "output"

            os.system(f"rm -rf {images_folder}")
            os.system(f"mkdir {images_folder}")

            os.system(f"rm -rf {output_folder}")
            os.system(f"mkdir {output_folder}")

            pdf_to_png("temp.pdf", images_folder, 300, lim)
            createXls(images_folder, output_folder, lim)

            output_file = f'{output_folder}/combined_sheets.xlsx'
            createCombinedXls(output_folder, output_file)

            # Calculate the amount to be charged
            amount_to_charge = max(0, (lim - 2) * 200)  # Rs 2 per page for more than 2 pages

            if amount_to_charge > 0:
                st.markdown("<h3 style='font-size: 15px;'>Payment Required</h3>", unsafe_allow_html=True)
                st.write(f"You need to pay Rs {amount_to_charge / 100} for {lim} pages.")

                # Create Razorpay order
                order = create_razorpay_order(amount_to_charge)
                order_id = order['id']

                # Razorpay payment button
                #callback_url = 'http://localhost:5000/razorpay_callback'  # Replace with your callback URL
                razorpay_options = {
                    'key': razorpay_key_id,
                    'amount': amount_to_charge,
                    'currency': 'INR',
                    'name': 'Your Company Name',
                    'description': 'Payment for Bank Statement Extraction',
                    'order_id': order_id,
                    'handler': function (response){
                        alert(response.razorpay_payment_id);
                        alert(response.razorpay_order_id);
                        alert(response.razorpay_signature)
                    },
                    'prefill': {
                        'name': 'User Name',
                        'email': 'shivanis1406@gmail.com',
                        'contact': '9654415614'
                    },
                    'notes': {
                        'address': 'Razorpay Corporate Office'
                    },
                    'theme': {
                        'color': '#F37254'
                    }
                }
                if st.button("Make Payment"):
                   st.markdown(f"""
                    <form>
                      <script
                        src="https://checkout.razorpay.com/v1/checkout.js"
                        data-key="{razorpay_options['key']}"
                        data-amount="{razorpay_options['amount']}"
                        data-currency="{razorpay_options['currency']}"
                        data-name="{razorpay_options['name']}"
                        data-description="{razorpay_options['description']}"
                        data-order_id="{razorpay_options['order_id']}"
                        data-prefill.name="{razorpay_options['prefill']['name']}"
                        data-prefill.email="{razorpay_options['prefill']['email']}"
                        data-prefill.contact="{razorpay_options['prefill']['contact']}"
                        data-notes.address="{razorpay_options['notes']['address']}"
                        data-theme.color="{razorpay_options['theme']['color']}"
                      ></script>
                      <input type="hidden" custom="Hidden Element" name="hidden">
                    </form>
                    <script>
                    var options = {
                        "key": "{razorpay_options['key']}",
                        "amount": "{razorpay_options['amount']}",
                        "currency": "{razorpay_options['currency']}",
                        "name": "{razorpay_options['name']}",
                        "description": "{razorpay_options['description']}",
                        "order_id": "{razorpay_options['order_id']}",
                        "handler": function (response){
                            alert(response.razorpay_payment_id);
                            alert(response.razorpay_order_id);
                            alert(response.razorpay_signature)
                        },
                        "prefill": {{
                            "name": "{razorpay_options['prefill']['name']}",
                            "email": "{razorpay_options['prefill']['email']}",
                            "contact": "{razorpay_options['prefill']['contact']}"
                        }},
                        "notes": {{
                            "address": "{razorpay_options['notes']['address']}"
                        }},
                        "theme": {{
                            "color": "{razorpay_options['theme']['color']}"
                        }}
                    };
                    var rzp1 = new Razorpay(options);
                    rzp1.on('payment.failed', function (response){
                            alert(response.error.code);
                            alert(response.error.description);
                            alert(response.error.source);
                            alert(response.error.step);
                            alert(response.error.reason);
                            alert(response.error.metadata.order_id);
                            alert(response.error.metadata.payment_id);
                    });
                    document.getElementById('rzp-button1').onclick = function(e){
                        rzp1.open();
                        e.preventDefault();
                    }
                    </script>
                    """, unsafe_allow_html=True)
            else:
                with open(output_file, "rb") as f:
                    st.download_button("Download Excel", f, file_name="BankStatement.xlsx")



if __name__ == "__main__":
    main()