import psycopg2, zipfile, re, xml.etree.ElementTree as ET
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(host='localhost', port=5432, dbname='india_dev_analytics', user='analyst', password='yash123')
cur = conn.cursor()

# Load LGD excel - get ALL district name -> code -> state code mappings
lgd_file = 'LGD - Local Government Directory, Government of India.xlsx'

with zipfile.ZipFile(lgd_file, 'r') as z:
    # First get shared strings if any
    shared_strings = []
    if 'xl/sharedStrings.xml' in z.namelist():
        with z.open('xl/sharedStrings.xml') as f:
            ss_root = ET.fromstring(f.read().decode('utf-8'))
            ns2 = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            for si in ss_root.findall('.//ns:si', ns2):
                texts = si.findall('.//ns:t', ns2)
                shared_strings.append(''.join(t.text or '' for t in texts))

    with z.open('xl/worksheets/sheet1.xml') as f:
        content = f.read().decode('utf-8')

root = ET.fromstring(content)
ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def get_cell_value(cell, shared_strings):
    t = cell.get('t', '')
    if t == 's':  # shared string
        v = cell.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
        if v is not None and v.text is not None:
            return shared_strings[int(v.text)]
    elif t == 'inlineStr':
        is_elem = cell.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}is')
        if is_elem is not None:
            t_elem = is_elem.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')
            return t_elem.text if t_elem is not None else ''
    else:
        v = cell.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
        return v.text if v is not None else ''
    return ''

# Print header row first
print("=== LGD FILE COLUMNS (first 3 rows) ===")
for row in root.findall('.//ns:row', ns):
    row_num = int(row.get('r', 0))
    if row_num > 3:
        break
    cells = {}
    for cell in row.findall('ns:c', ns):
        ref = cell.get('r', '')
        col = re.sub(r'\d', '', ref)
        cells[col] = get_cell_value(cell, shared_strings)
    print(f"Row {row_num}: {cells}")

# Now dump ALL rows for the unmatched districts we need
targets = [
    'adilabad', 'anantapur', 'hyderabad', 'karimnagar', 'khammam',
    'mahbubnagar', 'medak', 'nalgonda', 'nizamabad', 'rangareddy', 'warangal',
    'karimganj', 'morigaon', 'purba champaran', 'koriya',
    'dadra', 'daman', 'diu', 'ahmadabad', 'dohad',
    'gurgaon', 'mewat', 'lahul', 'badgam', 'bandipore', 'baramula',
    'kargil', 'leh', 'punch', 'shupiyan', 'kodarma', 'singhbhum',
    'sahibganj', 'bangalore', 'belgaum', 'bellary', 'bijapur',
    'chikmagalur', 'gulbarga', 'mysore', 'ramanagara', 'shimoga', 'tumkur',
    'hoshangabad', 'ahmadnagar', 'aurangabad', 'beed', 'buldana',
    'gondiya', 'osmanabad', 'raigad', 'ribhoi', 'saiha',
    'angul', 'balasore', 'boudh', 'deogarh', 'jajpur',
    'keonjhar', 'nabarangpur', 'subarnapur', 'mahe', 'pondicherry',
    'yanam', 'firozpur', 'mohali', 'chittorgarh', 'dholpur',
    'east sikkim', 'north sikkim', 'south sikkim', 'west sikkim',
    'allahabad', 'prayagraj', 'faizabad', 'ayodhya', 'amroha',
    'kanshiram', 'hathras', 'bhadohi', 'haridwar', 'hardwar',
    'bardhaman', 'darjeeling', 'howrah', 'hooghly', 'cooch behar',
    'north 24', 'purulia', 'south 24'
]

print("\n=== MATCHING LGD ROWS ===")
print("StateCode | DistCode | StateName | DistName")
for row in root.findall('.//ns:row', ns):
    row_num = int(row.get('r', 0))
    if row_num == 1:
        continue
    cells = {}
    for cell in row.findall('ns:c', ns):
        ref = cell.get('r', '')
        col = re.sub(r'\d', '', ref)
        cells[col] = get_cell_value(cell, shared_strings)
    
    dist_name = cells.get('E', '').lower()
    if any(t in dist_name for t in targets):
        sc = cells.get('B', '')
        dc = cells.get('D', '')
        sn = cells.get('C', '')
        dn = cells.get('E', '')
        print(f"  {sc} | {dc} | {sn} | {dn}")

conn.close()