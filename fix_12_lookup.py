import psycopg2, zipfile, re, xml.etree.ElementTree as ET
from dotenv import load_dotenv
load_dotenv()

lgd_file = 'LGD - Local Government Directory, Government of India.xlsx'

with zipfile.ZipFile(lgd_file, 'r') as z:
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

def get_val(cell):
    t = cell.get('t', '')
    ns0 = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    if t == 's':
        v = cell.find(f'{{{ns0}}}v')
        if v is not None and v.text is not None:
            return shared_strings[int(v.text)]
    elif t == 'inlineStr':
        is_elem = cell.find(f'{{{ns0}}}is')
        if is_elem is not None:
            t_elem = is_elem.find(f'{{{ns0}}}t')
            return t_elem.text if t_elem is not None else ''
    else:
        v = cell.find(f'{{{ns0}}}v')
        return v.text if v is not None else ''
    return ''

# Search for each district by partial name and state code
# Haryana=6, HP=2, UP=9, Bihar=10, Odisha=21, CG=22, Gujarat=24, AP=28, Karnataka=29, Assam=18
targets = {
    '6':  ['gurugram', 'gurgaon', 'nuh', 'mewat'],
    '2':  ['lahaul', 'lahul', 'spiti'],
    '9':  ['kanshiram', 'kasganj'],
    '10': ['east champaran', 'purba champaran', 'motihari'],
    '21': ['subarnapur', 'sonepur', 'nuapada'],
    '22': ['koriya', 'korea'],
    '24': ['ahmedabad', 'ahmadabad', 'dahod', 'dohad'],
    '28': ['anantapur', 'anantapuramu'],
    '29': ['ramanagara', 'ramanagar'],
    '18': ['kamrup'],
}

print("StateCode | DistCode | StateName | DistName")
for row in root.findall('.//ns:row', ns):
    row_num = int(row.get('r', 0))
    if row_num == 1:
        continue
    cells = {}
    for cell in row.findall('ns:c', ns):
        ref = cell.get('r', '')
        col = re.sub(r'\d', '', ref)
        cells[col] = get_val(cell)
    sc = cells.get('B', '')
    dn = cells.get('E', '').lower()
    if sc in targets and any(t in dn for t in targets[sc]):
        print(f"  {sc} | {cells.get('D','')} | {cells.get('C','')} | {cells.get('E','')}")