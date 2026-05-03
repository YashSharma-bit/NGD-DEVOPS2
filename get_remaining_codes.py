import zipfile, re, xml.etree.ElementTree as ET

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

def get_val(cell, shared_strings):
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

# Print all districts for these states by state code
# Assam=18, J&K=1, Ladakh=37, Karnataka=29, MP=23, Maharashtra=27
# Meghalaya=17, Mizoram=15, Odisha=21, Puducherry=34, Punjab=3
# Sikkim=11, WB=19, Jharkhand=20, Telangana=36
target_states = {'1','3','11','14','15','17','18','20','23','27','29','34','36','37','38'}

print("StateCode | DistCode | StateName | DistName")
for row in root.findall('.//ns:row', ns):
    row_num = int(row.get('r', 0))
    if row_num == 1:
        continue
    cells = {}
    for cell in row.findall('ns:c', ns):
        ref = cell.get('r', '')
        col = re.sub(r'\d', '', ref)
        cells[col] = get_val(cell, shared_strings)
    if cells.get('B', '') in target_states:
        print(f"  {cells.get('B','')} | {cells.get('D','')} | {cells.get('C','')} | {cells.get('E','')}")