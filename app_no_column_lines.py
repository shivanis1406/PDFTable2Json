import pdfplumber
import pandas as pd
import  os, re
import openpyxl
from datetime import datetime
from utils import extract_horizontal_lines_from_pdf

output_folder = "./output/"

os.system(f"rm -rf {output_folder}")
os.system(f"mkdir -p {output_folder}")

def extract_tables_with_best_strategy(pdf_path, start_pageno, end_pageno):
    strategies = [
        {"horizontal_strategy": "lines", "vertical_strategy": "lines"},
        {"horizontal_strategy": "text", "vertical_strategy": "text"},
        {"horizontal_strategy": "lines", "vertical_strategy": "text"},
        {"horizontal_strategy": "text", "vertical_strategy": "lines"}
    ]

    best_table = None
    best_strategy = None
    max_cells = 0

    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            if page_num != start_pageno - 1:
                continue

            for strategy in strategies:
                if 1:

                    # Crop the page to the bounding box
                    cropped_page = cropPage(page)
                    if cropped_page is None:
                        print("No table found with the given strategies.")
                        best_strategy = None
                        tables = []
                        break

                    # Extract the table from the cropped page
                    tables = cropped_page.extract_tables(strategy)
                else:
                    tables = page.extract_tables(strategy)

                print(f"Number of tables extracted from page {page_num}:", len(tables))

                for table in tables:
                    cell_count = sum(len(row) for row in table)
                    if cell_count > max_cells:
                        max_cells = cell_count
                        best_tables = tables
                        best_strategy = strategy

    if best_tables is not None:
        print(f"Best Strategy: {best_strategy}")
        all_tables = {}
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                if page_num > end_pageno - 1:
                    continue
                print("Page number is : ", page_num)
                if page_num == 0:
                    #tables = cropped_page.extract_tables(best_strategy)
                    tables = page.extract_words(keep_blank_chars=True, use_text_flow=True)
                else:
                    tables = page.extract_tables(best_strategy)
                print(f"Number of tables extracted from page {page_num}:", len(tables))
                print(tables)
                all_tables.update({page_num : [pd.DataFrame(table) for table in tables]})
        #for row in best_table:
        #    print(row)
        #Return a dict where every key, value pair represents list of dfs on that page
        return all_tables
    else:
        print(f"No table found with the given strategies.")
        return {}

# Function to save the tables in CSV and Excel format
def save_tables(dfs, base_filename, output_folder):
    xlsx_filename = f"{output_folder}/{base_filename}_combined.xlsx"
    print("Number of tables found: ", len(dfs))
    with pd.ExcelWriter(xlsx_filename) as writer:
            for j in range(len(dfs)):
                df = dfs[j]
                #print(df.head(50))
                sheet_name = f"Table_{j}"
                print(f"Writing to Excel file... {xlsx_filename} (Sheet: {sheet_name})")
                df.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"Combined Excel file saved as {xlsx_filename}")

def find_header_coordinates(pdf_path, end_pageno, start_pageno):
    x0s = []
    x1s = []
    texts = []
    bottoms = []
    end_indices = []
    start_indices = []
    all_lines = [[] for _ in range(start_pageno - 1, end_pageno)]

    header_pattern_withdate = re.compile(
                r"date.*balance.*withdrawal.*deposit|"
                r"date.*balance.*deposit.*withdrawal|"
                r"date.*withdrawal.*balance.*deposit|"
                r"date.*withdrawal.*deposit.*balance|"
                r"date.*deposit.*balance.*withdrawal|"
                r"date.*deposit.*withdrawal.*balance|"
                r"balance.*date.*withdrawal.*deposit|"
                r"balance.*date.*deposit.*withdrawal|"
                r"balance.*withdrawal.*date.*deposit|"
                r"balance.*withdrawal.*deposit.*date|"
                r"balance.*deposit.*date.*withdrawal|"
                r"balance.*deposit.*withdrawal.*date|"
                r"withdrawal.*date.*balance.*deposit|"
                r"withdrawal.*date.*deposit.*balance|"
                r"withdrawal.*balance.*date.*deposit|"
                r"withdrawal.*balance.*deposit.*date|"
                r"withdrawal.*deposit.*date.*balance|"
                r"withdrawal.*deposit.*balance.*date|"
                r"deposit.*date.*balance.*withdrawal|"
                r"deposit.*date.*withdrawal.*balance|"
                r"deposit.*balance.*date.*withdrawal|"
                r"deposit.*balance.*withdrawal.*date|"
                r"deposit.*withdrawal.*date.*balance|"
                r"deposit.*withdrawal.*balance.*date", 
                re.IGNORECASE
            )

    header_pattern = re.compile(
                r"balance.*withdrawal.*deposit|"
                r"balance.*deposit.*withdrawal|"
                r"withdrawal.*balance.*deposit|"
                r"withdrawal.*deposit.*balance|"
                r"deposit.*balance.*withdrawal|"
                r"deposit.*withdrawal.*balance|",
                re.IGNORECASE
    )
    
    start_index = -1
    end_index = -1
    words = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            #print("Page number is : ", page_num, start_pageno, end_pageno)
            if page_num < end_pageno and page_num >= start_pageno - 1:
                i = len(words)
                words.extend(page.extract_words())
                print("Starting from index ", i, "Number of words after adding page ", page_num," is : ", len(words))
                while i < len(words):
                    j = i + 1
                    start_index = i
                    while j < len(words) and words[j]['bottom'] - words[i]['bottom'] < 0.001:
                        j += 1
                    if (j < len(words) and words[j]['bottom'] - words[i]['bottom'] > 0.001) or (j >= len(words) and words[j - 1]['bottom'] - words[i]['bottom'] < 0.001):
                        end_index = j - 1
                        i = j
                        strr = " ".join([words[i]['text'] for i in range(start_index, end_index + 1)])
                        ##print("String is : ", strr)
                        #If the str is a row containing headers
                        if header_pattern_withdate.match(strr):
                            x0s.append([words[i]['x0'] for i in range(start_index, end_index + 1)])
                            x1s.append([words[i]['x1'] for i in range(start_index, end_index + 1)])
                            texts.append([words[i]['text'] for i in range(start_index, end_index + 1)])
                            bottoms.append([words[i]['bottom'] for i in range(start_index, end_index + 1)])   
                            end_indices.append(end_index)
                            start_indices.append(start_index)
                        elif header_pattern.match(strr):
                            #Check is 'date' is present in the next row. If yes, then it both rows combined is a header row
                            pass

                #Find lines on all the pages between start_pagno. and end_pageno.
                #all_lines.append(extract_horizontal_lines_from_pdf(pdf_path, page_num))
    print("length of start_indices is ", len(start_indices))
    print("length of end_indices is ", len(end_indices))
    return [x0s, x1s, texts, bottoms, end_indices, start_indices, words, all_lines]

# Helper function to check if a string is a date
def isDate(string):
    date_formats = [
        '%Y-%m-%d',  # 2023-04-10
        '%d-%m-%Y',  # 10-04-2023
        '%m-%d-%Y',  # 04-10-2023
        '%Y/%m/%d',  # 2023/04/10
        '%d/%m/%Y',  # 10/04/2023
        '%m/%d/%Y',  # 04/10/2023
        '%d/%m/%y',  # 10/04/23
        '%m/%d/%y',  # 04/10/23
        ]
    for fmt in date_formats:
            try:
                datetime.strptime(string, fmt)
                return True
            except ValueError:
                continue
    return False

def is_amount(string):
    # Remove commas, 'Cr', 'CR', and any other non-numeric characters
    cleaned_string = re.sub(r'[,CrCR]', '', string, flags=re.IGNORECASE)
    # Check if the cleaned string is a valid number
    return re.match(r'^\d+\.?\d*$', cleaned_string) is not None

def find_empty_spaces_between_headers(column_headers, x0s, x1s):
    empty_spaces_between_headers = []
    #Start from x1[0:] and x0[1:] and find the difference between them. If the difference is greater than 0.001, then there is an empty space between the headers.
    for i in range(1, len(x0s)):
        empty_spaces_between_headers.append([x1s[i - 1], x0s[i]])
    return empty_spaces_between_headers

def isWordBetweenHeaders(word_x0, word_x1, empty_spaces_between_headers):
    for i in range(len(empty_spaces_between_headers) - 1):
        #print("Checking if word ", word_x0, word_x1, "is between ", empty_spaces_between_headers[i][0], " and ", empty_spaces_between_headers[i][1])
        if word_x0 > empty_spaces_between_headers[i][0] and word_x1 < empty_spaces_between_headers[i][1]:
            return (i, i+1)
    return (-1, -1)

def find_column_header(word, headerA, headerB):
    text_under_headerA = ""
    text_under_headerB = ""
    #headerA
    if 'date' in headerA and isDate(word):
        text_under_headerA = word
    elif ('balance' in headerA or 'withdrawal' in headerA or 'deposit' in headerA) and is_amount(word):
        text_under_headerA = word
    elif ('narration' in headerA or 'particulars' in headerA) and not isDate(word) and not is_amount(word):
        text_under_headerA = word
    else:
        pass
    #headerB
    if 'date' in headerB and isDate(word):
        text_under_headerB = word
    elif ('balance' in headerB or 'withdrawal' in headerB or 'deposit' in headerB) and is_amount(word):
        text_under_headerB = word
    elif ('narration' in headerB or 'particulars' in headerB) and not isDate(word) and not is_amount(word):
        text_under_headerB = word
    else:
        pass
    return (text_under_headerA, text_under_headerB)

def isValidRow(words, row_index, end_index, x0s, x1s):
    #Create a string from the words and check if it is a valid row. Only for tables that do not have vertical lines separating columns
    i = row_index
    #print("Row index is ", row_index, "End index is ", end_index)
    strr = ""
    #print("Checking if row at index ", row_index, "is valid or not......")
    last_word_was_date = False

    while i <= end_index and abs(words[i]['bottom'] - words[row_index]['bottom']) < 0.001:
        #print("Word is ", words[i]['text'], "i is ", i)
        #";" is the delimiter between columns

        #if the word contains "summary" or "cumulative", return (False, -1, "END") to denote end of table
        if 'summary' in words[i]['text'].lower() or 'cumulative' in words[i]['text'].lower():
                strr += words[i]['text']
                return (strr, False, i, "END")

        if i == row_index:
            #If the first word is a date then add to strr += words[i]['text']
            if isDate(words[i]['text']):
                strr += words[i]['text']
                last_word_was_date = True
                last_header_index = 0
            #If the first word is not a date, then words[i]['x0'] must be greater than x1s[0]. If yes, then add to str += ";" + words[i]['text']
            if not isDate(words[i]['text']):
                if words[i]['x0'] < x1s[0]:
                    strr += words[i]['text']
                    return (strr, False, i, "")

                j = 0
                while j < len(x1s) and words[i]['x0'] > x1s[j]:
                    #Keep appending ";" until words[i]['x0'] > x1s[j]
                    strr += ";"
                    j += 1
                strr += words[i]['text']
                last_header_index = j

        #Go over other words such that
        else:
            if last_word_was_date:
                strr += ";" + words[i]['text']
                last_header_index += 1
                last_word_was_date = False

            else:
                if words[i]['x1'] < x0s[last_header_index + 1] and words[i]['x1'] > x1s[last_header_index]:
                    #print("Word is between two headers but table does not have vertical lines separating columns. Assuming left alignment of text")
                    strr += " " + words[i]['text']
                else:
                    j = last_header_index + 1
                    while j < len(x0s) and words[i]['x1'] > x0s[j]:
                        #print("j is ", j, "len(x0s) is ", len(x0s), "words[i]['x1'] is ", words[i]['x1'], "x0s[j] is ", x0s[j])
                        #word is between two headers but table does not have vertical lines separating columns. 
                        strr += ";"
                        j += 1
                    last_header_index = j - 1
                    strr += words[i]['text']



            if isDate(words[i]['text']):
                last_word_was_date = True
        i += 1

        while (i <=end_index and abs(words[i]['bottom'] - words[row_index]['bottom']) > 0.001) or i > end_index:
            if len(strr.split(";")) < len(x0s):
                #Append empty strings to strr until the length of strr is equal to the number of headers
                strr += ";"
            else:
                break

    #print("String is ", strr)
    return (strr, True, i, "")


def create_table(all_words, start_index, end_index, column_headers, x0s, x1s, Hlines):
    # Create a DataFrame with headers as column_headers
    df = pd.DataFrame(columns=column_headers)
    
    row_index = start_index
    empty_spaces_between_headers = find_empty_spaces_between_headers(column_headers, x0s, x1s)
    print("Empty spaces between headers are ", empty_spaces_between_headers)
    print("Row index is ", row_index, "End index is ", end_index)

    while row_index <= end_index:
        #go till end_index until you find a horizontal line after reading a few valid table rows
        current_row = [""] * len(column_headers)  # Initialize a new row with empty strings
        col_index = row_index

        #Check if row is valid or not. First word must be a date
        (strr, is_valid_row, new_row_index, endOfTable) = isValidRow(all_words, row_index, end_index, x0s, x1s)
        #print("Is row valid? ", is_valid_row, "End of table? ", endOfTable)
        #print("Row is ", strr)

        if is_valid_row == True and endOfTable != "END":
            #Move to the next row
            row_index = new_row_index
            print("Row is valid", strr, " and Next row is ", row_index)
            #Current row
            #print([strr.split(";")])
            df = pd.concat([df, pd.DataFrame([strr.split(";")], columns=column_headers)], ignore_index=True)
            continue
            
        if is_valid_row == False and endOfTable != "END":
            #Increment row_index to move to the next row
            col_index = new_row_index
            while col_index <= end_index and abs(all_words[col_index]['bottom'] - all_words[row_index]['bottom']) < 0.001:
                col_index += 1
            row_index = col_index
            print("Row", strr, "is not valid. Moving to the next row.", row_index)
            continue

        if endOfTable == "END" or row_index > end_index:
            print("End of table reached")
            break

    print("Table is :")
    print(df.head(10))  # Print the first 10 rows for verification
    return df


def showHeaders(pdf_path, end_pageno, start_pageno):

    [x0s, x1s, headers, bottoms, end_indices, start_indices, all_words, all_lines] = find_header_coordinates(pdf_path, end_pageno, start_pageno)
    #lines is from all pages between start and end_pageno, lines[0], lines[1]... where 0 means page 1, 1 means page 2.
    dfs = []

    if len(end_indices) == 0:
            print("Header row not found.")

    for page_num in range(start_pageno - 1, end_pageno):
        print("Page number is ", page_num)
        print("Start index is ", start_indices[page_num])
        print("End index is ", end_indices[page_num])
        print("Header row coordinates: ")
        print(x0s[page_num])
        print("######################")
        print(x1s[page_num])
        print("######################")
        print(headers[page_num])



        strr = ""
        maxx = 0

        for j in range(len(x0s[page_num]) - 1):
            strr+="{}--->{}".format(headers[page_num][j], x0s[page_num][j+1] - x1s[page_num][j])
            strr+="--->"
            if maxx < x0s[page_num][j+1] - x1s[page_num][j]:
                maxx = x0s[page_num][j+1] - x1s[page_num][j]

        strr+="{}".format(headers[page_num][j+1])
        print(strr)

        strr = ""
        column_headers = []
        k = 0
        while k < len(x0s[page_num]):
            #print("k is ",k, "writing ",words[i][k])
            strr += headers[page_num][k]
            m = k + 1
            while m < len(x0s[page_num]) - 1 and x0s[page_num][m] - x1s[page_num][m - 1] < (maxx/20):
                strr += "_" + headers[page_num][m]
                m = m + 1
                #print(strr,m)
            column_headers.append(strr)
            strr = ""
            k = m

        print("Column Headers are ",column_headers)

        #words is the list of words from the entire pdf till page end_pageno.
        #Start looping over words from words[end_index + 1] till the next time you match head_pattern and find the table
        

        if page_num < end_pageno - 1:
            print("Page number is ", page_num)
            start_index = end_indices[page_num] + 1
            end_index = start_indices[page_num + 1] - 1
            df = create_table(all_words, start_index, end_index, column_headers, x0s[page_num], x1s[page_num], all_lines[page_num])
        else:
            #Last page
            print("Last page")
            start_index = end_indices[page_num] + 1
            df = create_table(all_words, start_index, len(all_words) - 1, column_headers, x0s[page_num], x1s[page_num], all_lines[page_num])
        
        dfs.append(df)

    return dfs

pdf_path = "./Apr-24.pdf"
#pdf_path = "Acct Statement_XX6820_02082024.pdf"
#pdf_path = "rajuram ac statement.pdf"
#Start Page always has table headers - Assumption!. Always start from the first page.
start_pageno = 1
end_pageno = 3

dfs = showHeaders(pdf_path, end_pageno, start_pageno)
save_tables(dfs, 'table_', output_folder)
