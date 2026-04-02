import fitz
import re
from jinja2 import Template, FileSystemLoader, Environment
from datetime import datetime
from weasyprint import HTML
import requests
from mail import send_email
from bs4 import BeautifulSoup
import os
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.wrappers import request

env = Environment(loader=FileSystemLoader('.'))
input_path = "C:/Dixio/SyncAppProd/folders/reception/LTA/Outgoing"
# input_path = "./Inputfiles"
def get_readable_summary(pdf_path):
    doc = fitz.open(pdf_path)
    doc_transactions = []
    pages = doc.page_count
    for i in range(0,pages,3):
        transaction_pages = doc[i:i+3]

            # Initialize the data structure to hold our results
        extracted_data = {
            "header": {},
            "transactions": [],
            "metadata": {"file_path": pdf_path, "status": "success"}
        }

        try:

            raw_text = ""
            for page in transaction_pages:
                # Preserve whitespace to avoid words sticking together
                raw_text += page.get_text("text", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        except Exception as e:
            return {"header": {}, "transactions": [], "metadata": {"file_path": pdf_path, "status": "error", "message": str(e)}}

        # 1. Pre-process the text
        # Remove excessive newlines but keep the tag structure intact
        clean_text = re.sub(r'\s+', ' ', raw_text)
        message_ref = raw_text[398:438]

        # 2. Extract specific patterns (Key-Value pairs)
        # Since the document isn't pure XML, we look for the tags directly in the text stream
        def find_tag_content(tag_name, text):
            pattern = rf'<{tag_name}[^>]*>(.*?)</{tag_name}>'
            match = re.search(pattern, text, re.IGNORECASE)
            return match.group(1).strip() if match else None

        def find_attribute(tag_name, attr_name, text):
            # Specifically for things like <IntrBkSttlmAmt Ccy="USD">
            pattern = rf'<{tag_name}[^>]*{attr_name}="([^"]*)"'
            match = re.search(pattern, text, re.IGNORECASE)
            return match.group(1) if match else None

        # 3. Extract Global Header Info (MsgId and CreDtTm)
        msg_id = find_tag_content('MsgId', clean_text)
        creation_date = find_tag_content('CreDtTm', clean_text) or find_tag_content('CreDt', clean_text)
        print(creation_date)
        extracted_data["header"] = {
            "message_id": msg_id,
            "messageRef": message_ref,
            "creation_date": datetime.fromisoformat(creation_date).strftime(("%d %b %Y, %I:%M %p"))
        }
        # print(extracted_data)
        # 4. Identify Transaction Blocks
        tx_blocks = re.findall(r'<CdtTrfTxInf[^>]*>(.*?)</CdtTrfTxInf>', clean_text, re.IGNORECASE)

        for i, block in enumerate(tx_blocks, 1):
            # Extract individual fields from the block
            uetr = find_tag_content('UETR', block)
            amt = find_tag_content('IntrBkSttlmAmt', block)
            ccy = find_attribute('IntrBkSttlmAmt', 'Ccy', block)
            dt = find_tag_content('IntrBkSttlmDt', block)
            ref = find_tag_content('RmtInf', block)



            # Sender (Debtor) - Look for Nm inside Dbtr block
            dbtr_match = re.search(r'<Dbtr[^>]*>(.*?)</Dbtr>', block, re.IGNORECASE)
            dbtr_name = find_tag_content('Nm', dbtr_match.group(1)) if dbtr_match else None

            # Receiver (Creditor) - Look for Nm inside Cdtr block
            cdtr_match = re.search(r'<Cdtr[^>]*>(.*?)</Cdtr>', block, re.IGNORECASE)
            cdtr_name = find_tag_content('Nm', cdtr_match.group(1)) if cdtr_match else None

            bic_match = find_tag_content('FinInstnId', cdtr_match.group())
            bic =  find_tag_content('BICFI', bic_match) if bic_match else None

            status, data = get_bic(bic)
            bic = data['institutionName'] if status==200 else bic

            acc_number_match = re.search(r'<CdtrAcct[^>]*>(.*)</CdtrAcct>', block, re.IGNORECASE)
            acc_number = find_tag_content('Id', acc_number_match.group(1)) if acc_number_match else None


            # Account Info
            iban = find_tag_content('IBAN', block)

            # Append structured transaction data
            extracted_data["transactions"].append({
                "transaction_index": i,
                "UETR": uetr,
                "Amount": amt,
                "Currency": ccy,
                "SenderName": dbtr_name,
                "ReceiverName": cdtr_name,
                "IBAN": acc_number,
                "Reference": ref,
                'FINInstnId': bic,

            })
            doc_transactions.append(extracted_data)
    return doc_transactions


def get_bic(bic):
    endpoint =  f"http://10.10.130.11:3000/api/bidc_ir/bic-code/{bic}"
    response =  requests.get(endpoint)
    status = response.status_code
    return status, response.json()


def identify_swift_type(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        header_text = ""
        for i in range(min(2, len(doc))):
            header_text += doc[i].get_text("text")


        mx_indicators = [
            'urn:iso:std:iso:20022',
            '<AppHdr',
            '<Document',
            'pacs.008',
            'pain.001'
        ]


        mt_indicators = [
            '{1:F01',
            '{4:',
            ':20:',
            ':32A:',
            'SWIFT MT'
        ]

        if any(ind in header_text for ind in mx_indicators):
            return "MX"
        elif any(ind in header_text for ind in mt_indicators):
            return "MT"

        return "UNKNOWN"
    except Exception as e:
        print(f"Error identifying {pdf_path}: {e}")
        return "ERROR"


def generate_html(mx_data, file):

    template = env.get_template("template.html")
    context = {'MessageID': mx_data['header']['message_id'],
               'CreationTimestamp': mx_data['header']['creation_date'],
               'Transactions': mx_data.get('transactions', []),
               'MessageRef': mx_data['header']['messageRef'],
               'GenerationDate': datetime.now().strftime(("%d %b %Y, %I:%M %p"))}

    html = template.render(context)
    HTML(string=html, base_url= '.').write_pdf(f"./Outputfiles/{file}")
    return file
    # template.render(context)


def send_new_message():
    inputfiles = os.listdir(input_path)
    outputfiles = os.listdir("./Outputfiles")
    outputfiles = [outputfile.rstrip('_') for outputfile in outputfiles]
    missing_files = set(inputfiles) - set(outputfiles)
    # print(missing_files)
    new_files = []
    for file in missing_files:
        if file.endswith('.pdf'):
            if identify_swift_type(f"{input_path}/{file}") == "MX":
                transactions = get_readable_summary(f"{input_path}/{file}")
                for transaction in transactions:
                    file_name = generate_html(transaction, file.strip('.pdf') +f'_{transaction['header']['message_id']}.pdf')
                    print(file_name)
                new_files.append(file_name)
            else:
                pass
    if len(new_files) > 0:
        # send_new_message(new_files)
        with open('./email_template.html', 'r', encoding='latin1') as f:
            email_html = f.read()
        send_email(recipients=[
            'jmusa@bidc-ebid.org',
            'EOMIJIE@bidc-ebid.org',
            'aouattara@bidc-ebid.org',
            'YDETE@bidc-ebid.org',
            'AAMANKWAH@bidc-ebid.org'
            'forimoloye@bidc-ebid.org'
        ],
            cc=[],
            subject="New LTA Message Received",
            body=Template(email_html).render(),
            attachments=new_files,
            inline_images=[
                "./static/images/image001.jpg",
                "./static/images/image003.gif",
                "./static/images/image005.jpg",
                "./static/images/image007.jpg",
                "./static/images/image009.jpg",
                "./static/images/image011.jpg",
                "./static/images/image013.jpg",
            ],

        )

send_new_message()
if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_new_message, 'interval', minutes=5)
    scheduler.start()

    try:
        while True:
            pass
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

