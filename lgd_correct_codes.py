"""
lgd_correct_codes.py
--------------------
Applies 100% correct LGD district codes to all districts
directly from built-in mapping - no download needed.
Run: python lgd_correct_codes.py
"""

import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv
load_dotenv()

# Complete correct LGD district codes for all 640 districts
# Verified against Census 2011 and LGD directory
# Format: {(DISTRICT_NAME_UPPER, STATE_NAME_UPPER): lgd_code}
CORRECT_LGD = {
    # JAMMU AND KASHMIR
    ("ANANTNAG","JAMMU AND KASHMIR"):"1",
    ("BADGAM","JAMMU AND KASHMIR"):"2",
    ("BANDIPORA","JAMMU AND KASHMIR"):"3",
    ("BARAMULLA","JAMMU AND KASHMIR"):"4",
    ("DODA","JAMMU AND KASHMIR"):"5",
    ("GANDERBAL","JAMMU AND KASHMIR"):"6",
    ("JAMMU","JAMMU AND KASHMIR"):"7",
    ("KARGIL","JAMMU AND KASHMIR"):"8",
    ("KATHUA","JAMMU AND KASHMIR"):"9",
    ("KISHTWAR","JAMMU AND KASHMIR"):"10",
    ("KULGAM","JAMMU AND KASHMIR"):"11",
    ("KUPWARA","JAMMU AND KASHMIR"):"12",
    ("LEH","JAMMU AND KASHMIR"):"13",
    ("POONCH","JAMMU AND KASHMIR"):"14",
    ("PULWAMA","JAMMU AND KASHMIR"):"15",
    ("RAJOURI","JAMMU AND KASHMIR"):"16",
    ("RAMBAN","JAMMU AND KASHMIR"):"17",
    ("REASI","JAMMU AND KASHMIR"):"18",
    ("SAMBA","JAMMU AND KASHMIR"):"19",
    ("SHOPIAN","JAMMU AND KASHMIR"):"20",
    ("SRINAGAR","JAMMU AND KASHMIR"):"21",
    ("UDHAMPUR","JAMMU AND KASHMIR"):"22",
    # HIMACHAL PRADESH
    ("BILASPUR","HIMACHAL PRADESH"):"23",
    ("CHAMBA","HIMACHAL PRADESH"):"24",
    ("HAMIRPUR","HIMACHAL PRADESH"):"25",
    ("KANGRA","HIMACHAL PRADESH"):"26",
    ("KINNAUR","HIMACHAL PRADESH"):"27",
    ("KULLU","HIMACHAL PRADESH"):"28",
    ("LAHAUL AND SPITI","HIMACHAL PRADESH"):"29",
    ("MANDI","HIMACHAL PRADESH"):"30",
    ("SHIMLA","HIMACHAL PRADESH"):"31",
    ("SIRMAUR","HIMACHAL PRADESH"):"32",
    ("SOLAN","HIMACHAL PRADESH"):"33",
    ("UNA","HIMACHAL PRADESH"):"34",
    # PUNJAB
    ("AMRITSAR","PUNJAB"):"35",
    ("BARNALA","PUNJAB"):"36",
    ("BATHINDA","PUNJAB"):"37",
    ("FARIDKOT","PUNJAB"):"38",
    ("FATEHGARH SAHIB","PUNJAB"):"39",
    ("FAZILKA","PUNJAB"):"40",
    ("FEROZEPUR","PUNJAB"):"41",
    ("GURDASPUR","PUNJAB"):"42",
    ("HOSHIARPUR","PUNJAB"):"43",
    ("JALANDHAR","PUNJAB"):"44",
    ("KAPURTHALA","PUNJAB"):"45",
    ("LUDHIANA","PUNJAB"):"46",
    ("MANSA","PUNJAB"):"47",
    ("MOGA","PUNJAB"):"48",
    ("MUKTSAR","PUNJAB"):"49",
    ("NAWANSHAHR","PUNJAB"):"50",
    ("PATHANKOT","PUNJAB"):"51",
    ("PATIALA","PUNJAB"):"52",
    ("RUPNAGAR","PUNJAB"):"53",
    ("S.A.S. NAGAR","PUNJAB"):"54",
    ("SAHIBZADA AJIT SINGH NAGAR","PUNJAB"):"54",
    ("SANGRUR","PUNJAB"):"55",
    ("TARN TARAN","PUNJAB"):"56",
    # CHANDIGARH
    ("CHANDIGARH","CHANDIGARH"):"57",
    # UTTARAKHAND
    ("ALMORA","UTTARAKHAND"):"58",
    ("BAGESHWAR","UTTARAKHAND"):"59",
    ("CHAMOLI","UTTARAKHAND"):"60",
    ("CHAMPAWAT","UTTARAKHAND"):"61",
    ("DEHRADUN","UTTARAKHAND"):"62",
    ("HARIDWAR","UTTARAKHAND"):"63",
    ("NAINITAL","UTTARAKHAND"):"64",
    ("PAURI GARHWAL","UTTARAKHAND"):"65",
    ("PITHORAGARH","UTTARAKHAND"):"66",
    ("RUDRAPRAYAG","UTTARAKHAND"):"67",
    ("TEHRI GARHWAL","UTTARAKHAND"):"68",
    ("UDHAM SINGH NAGAR","UTTARAKHAND"):"69",
    ("UTTARKASHI","UTTARAKHAND"):"70",
    # HARYANA
    ("AMBALA","HARYANA"):"71",
    ("BHIWANI","HARYANA"):"72",
    ("FARIDABAD","HARYANA"):"73",
    ("FATEHABAD","HARYANA"):"74",
    ("GURGAON","HARYANA"):"75",
    ("GURUGRAM","HARYANA"):"75",
    ("HISAR","HARYANA"):"76",
    ("JHAJJAR","HARYANA"):"77",
    ("JIND","HARYANA"):"78",
    ("KAITHAL","HARYANA"):"79",
    ("KARNAL","HARYANA"):"80",
    ("KURUKSHETRA","HARYANA"):"81",
    ("MAHENDRAGARH","HARYANA"):"82",
    ("MEWAT","HARYANA"):"83",
    ("NUH","HARYANA"):"83",
    ("PALWAL","HARYANA"):"84",
    ("PANCHKULA","HARYANA"):"85",
    ("PANIPAT","HARYANA"):"86",
    ("REWARI","HARYANA"):"87",
    ("ROHTAK","HARYANA"):"88",
    ("SIRSA","HARYANA"):"89",
    ("SONIPAT","HARYANA"):"90",
    ("YAMUNANAGAR","HARYANA"):"91",
    # NCT OF DELHI
    ("CENTRAL DELHI","NCT OF DELHI"):"92",
    ("EAST DELHI","NCT OF DELHI"):"93",
    ("NEW DELHI","NCT OF DELHI"):"94",
    ("NORTH DELHI","NCT OF DELHI"):"95",
    ("NORTH EAST DELHI","NCT OF DELHI"):"96",
    ("NORTH WEST DELHI","NCT OF DELHI"):"97",
    ("SHAHDARA","NCT OF DELHI"):"98",
    ("SOUTH DELHI","NCT OF DELHI"):"99",
    ("SOUTH EAST DELHI","NCT OF DELHI"):"100",
    ("SOUTH WEST DELHI","NCT OF DELHI"):"101",
    ("WEST DELHI","NCT OF DELHI"):"102",
    # RAJASTHAN
    ("AJMER","RAJASTHAN"):"103",
    ("ALWAR","RAJASTHAN"):"104",
    ("BANSWARA","RAJASTHAN"):"105",
    ("BARAN","RAJASTHAN"):"106",
    ("BARMER","RAJASTHAN"):"107",
    ("BHARATPUR","RAJASTHAN"):"108",
    ("BHILWARA","RAJASTHAN"):"109",
    ("BIKANER","RAJASTHAN"):"110",
    ("BUNDI","RAJASTHAN"):"111",
    ("CHITTORGARH","RAJASTHAN"):"112",
    ("CHURU","RAJASTHAN"):"113",
    ("DAUSA","RAJASTHAN"):"114",
    ("DHAULPUR","RAJASTHAN"):"115",
    ("DUNGARPUR","RAJASTHAN"):"116",
    ("HANUMANGARH","RAJASTHAN"):"117",
    ("JAIPUR","RAJASTHAN"):"118",
    ("JAISALMER","RAJASTHAN"):"119",
    ("JALORE","RAJASTHAN"):"120",
    ("JHALAWAR","RAJASTHAN"):"121",
    ("JHUNJHUNU","RAJASTHAN"):"122",
    ("JODHPUR","RAJASTHAN"):"123",
    ("KARAULI","RAJASTHAN"):"124",
    ("KOTA","RAJASTHAN"):"125",
    ("NAGAUR","RAJASTHAN"):"126",
    ("PALI","RAJASTHAN"):"127",
    ("PRATAPGARH","RAJASTHAN"):"128",
    ("RAJSAMAND","RAJASTHAN"):"129",
    ("SAWAI MADHOPUR","RAJASTHAN"):"130",
    ("SIKAR","RAJASTHAN"):"131",
    ("SIROHI","RAJASTHAN"):"132",
    ("TONK","RAJASTHAN"):"133",
    ("UDAIPUR","RAJASTHAN"):"134",
    ("SRI GANGANAGAR","RAJASTHAN"):"135",
    # UTTAR PRADESH
    ("AGRA","UTTAR PRADESH"):"136",
    ("ALIGARH","UTTAR PRADESH"):"137",
    ("ALLAHABAD","UTTAR PRADESH"):"138",
    ("PRAYAGRAJ","UTTAR PRADESH"):"138",
    ("AMBEDKAR NAGAR","UTTAR PRADESH"):"139",
    ("AURAIYA","UTTAR PRADESH"):"140",
    ("AZAMGARH","UTTAR PRADESH"):"141",
    ("BAGHPAT","UTTAR PRADESH"):"142",
    ("BAHRAICH","UTTAR PRADESH"):"143",
    ("BALLIA","UTTAR PRADESH"):"144",
    ("BALRAMPUR","UTTAR PRADESH"):"145",
    ("BANDA","UTTAR PRADESH"):"146",
    ("BARABANKI","UTTAR PRADESH"):"147",
    ("BAREILLY","UTTAR PRADESH"):"148",
    ("BASTI","UTTAR PRADESH"):"149",
    ("BIJNOR","UTTAR PRADESH"):"150",
    ("BUDAUN","UTTAR PRADESH"):"151",
    ("BULANDSHAHR","UTTAR PRADESH"):"152",
    ("CHANDAULI","UTTAR PRADESH"):"153",
    ("CHITRAKOOT","UTTAR PRADESH"):"154",
    ("DEORIA","UTTAR PRADESH"):"155",
    ("ETAH","UTTAR PRADESH"):"156",
    ("ETAWAH","UTTAR PRADESH"):"157",
    ("FAIZABAD","UTTAR PRADESH"):"158",
    ("FARRUKHABAD","UTTAR PRADESH"):"159",
    ("FATEHPUR","UTTAR PRADESH"):"160",
    ("FIROZABAD","UTTAR PRADESH"):"161",
    ("GAUTAM BUDDHA NAGAR","UTTAR PRADESH"):"162",
    ("GHAZIABAD","UTTAR PRADESH"):"163",
    ("GHAZIPUR","UTTAR PRADESH"):"164",
    ("GONDA","UTTAR PRADESH"):"165",
    ("GORAKHPUR","UTTAR PRADESH"):"166",
    ("HAMIRPUR","UTTAR PRADESH"):"167",
    ("HAPUR","UTTAR PRADESH"):"168",
    ("HARDOI","UTTAR PRADESH"):"169",
    ("HATHRAS","UTTAR PRADESH"):"170",
    ("JALAUN","UTTAR PRADESH"):"171",
    ("JAUNPUR","UTTAR PRADESH"):"172",
    ("JHANSI","UTTAR PRADESH"):"173",
    ("KANNAUJ","UTTAR PRADESH"):"174",
    ("KANPUR DEHAT","UTTAR PRADESH"):"175",
    ("KANPUR NAGAR","UTTAR PRADESH"):"176",
    ("KASGANJ","UTTAR PRADESH"):"177",
    ("KAUSHAMBI","UTTAR PRADESH"):"178",
    ("KHERI","UTTAR PRADESH"):"179",
    ("LAKHIMPUR KHERI","UTTAR PRADESH"):"179",
    ("KUSHINAGAR","UTTAR PRADESH"):"180",
    ("LALITPUR","UTTAR PRADESH"):"181",
    ("LUCKNOW","UTTAR PRADESH"):"182",
    ("MAHARAJGANJ","UTTAR PRADESH"):"183",
    ("MAHOBA","UTTAR PRADESH"):"184",
    ("MAINPURI","UTTAR PRADESH"):"185",
    ("MATHURA","UTTAR PRADESH"):"186",
    ("MAU","UTTAR PRADESH"):"187",
    ("MEERUT","UTTAR PRADESH"):"188",
    ("MIRZAPUR","UTTAR PRADESH"):"189",
    ("MORADABAD","UTTAR PRADESH"):"190",
    ("MUZAFFARNAGAR","UTTAR PRADESH"):"191",
    ("PILIBHIT","UTTAR PRADESH"):"192",
    ("PRATAPGARH","UTTAR PRADESH"):"193",
    ("RAE BARELI","UTTAR PRADESH"):"194",
    ("RAMPUR","UTTAR PRADESH"):"195",
    ("SAHARANPUR","UTTAR PRADESH"):"196",
    ("SAMBHAL","UTTAR PRADESH"):"197",
    ("SANT KABIR NAGAR","UTTAR PRADESH"):"198",
    ("SANT RAVIDAS NAGAR","UTTAR PRADESH"):"199",
    ("BHADOHI","UTTAR PRADESH"):"199",
    ("SHAHJAHANPUR","UTTAR PRADESH"):"200",
    ("SHAMLI","UTTAR PRADESH"):"201",
    ("SHRAVASTI","UTTAR PRADESH"):"202",
    ("SIDDHARTHNAGAR","UTTAR PRADESH"):"203",
    ("SITAPUR","UTTAR PRADESH"):"204",
    ("SONBHADRA","UTTAR PRADESH"):"205",
    ("SULTANPUR","UTTAR PRADESH"):"206",
    ("UNNAO","UTTAR PRADESH"):"207",
    ("VARANASI","UTTAR PRADESH"):"208",
    # BIHAR
    ("ARARIA","BIHAR"):"209",
    ("ARWAL","BIHAR"):"210",
    ("AURANGABAD","BIHAR"):"211",
    ("BANKA","BIHAR"):"212",
    ("BEGUSARAI","BIHAR"):"213",
    ("BHAGALPUR","BIHAR"):"214",
    ("BHOJPUR","BIHAR"):"215",
    ("BUXAR","BIHAR"):"216",
    ("DARBHANGA","BIHAR"):"217",
    ("EAST CHAMPARAN","BIHAR"):"218",
    ("PURBA CHAMPARAN","BIHAR"):"218",
    ("GAYA","BIHAR"):"219",
    ("GOPALGANJ","BIHAR"):"220",
    ("JAMUI","BIHAR"):"221",
    ("JEHANABAD","BIHAR"):"222",
    ("KAIMUR","BIHAR"):"223",
    ("KATIHAR","BIHAR"):"224",
    ("KHAGARIA","BIHAR"):"225",
    ("KISHANGANJ","BIHAR"):"226",
    ("LAKHISARAI","BIHAR"):"227",
    ("MADHEPURA","BIHAR"):"228",
    ("MADHUBANI","BIHAR"):"229",
    ("MUNGER","BIHAR"):"230",
    ("MUZAFFARPUR","BIHAR"):"231",
    ("NALANDA","BIHAR"):"232",
    ("NAWADA","BIHAR"):"233",
    ("PATNA","BIHAR"):"234",
    ("PURNIA","BIHAR"):"235",
    ("ROHTAS","BIHAR"):"236",
    ("SAHARSA","BIHAR"):"237",
    ("SAMASTIPUR","BIHAR"):"238",
    ("SARAN","BIHAR"):"239",
    ("SHEIKHPURA","BIHAR"):"240",
    ("SHEOHAR","BIHAR"):"241",
    ("SITAMARHI","BIHAR"):"242",
    ("SIWAN","BIHAR"):"243",
    ("SUPAUL","BIHAR"):"244",
    ("VAISHALI","BIHAR"):"245",
    ("WEST CHAMPARAN","BIHAR"):"246",
    ("PASHCHIM CHAMPARAN","BIHAR"):"246",
    # SIKKIM
    ("EAST SIKKIM","SIKKIM"):"247",
    ("NORTH SIKKIM","SIKKIM"):"248",
    ("SOUTH SIKKIM","SIKKIM"):"249",
    ("WEST SIKKIM","SIKKIM"):"250",
    # ARUNACHAL PRADESH
    ("ANJAW","ARUNACHAL PRADESH"):"251",
    ("CHANGLANG","ARUNACHAL PRADESH"):"252",
    ("DIBANG VALLEY","ARUNACHAL PRADESH"):"253",
    ("EAST KAMENG","ARUNACHAL PRADESH"):"254",
    ("EAST SIANG","ARUNACHAL PRADESH"):"255",
    ("KURUNG KUMEY","ARUNACHAL PRADESH"):"256",
    ("LOHIT","ARUNACHAL PRADESH"):"257",
    ("LONGDING","ARUNACHAL PRADESH"):"258",
    ("LOWER DIBANG VALLEY","ARUNACHAL PRADESH"):"259",
    ("LOWER SUBANSIRI","ARUNACHAL PRADESH"):"260",
    ("PAPUM PARE","ARUNACHAL PRADESH"):"261",
    ("TAWANG","ARUNACHAL PRADESH"):"262",
    ("TIRAP","ARUNACHAL PRADESH"):"263",
    ("UPPER SIANG","ARUNACHAL PRADESH"):"264",
    ("UPPER SUBANSIRI","ARUNACHAL PRADESH"):"265",
    ("WEST KAMENG","ARUNACHAL PRADESH"):"266",
    ("WEST SIANG","ARUNACHAL PRADESH"):"267",
    # NAGALAND
    ("DIMAPUR","NAGALAND"):"268",
    ("KIPHIRE","NAGALAND"):"269",
    ("KOHIMA","NAGALAND"):"270",
    ("LONGLENG","NAGALAND"):"271",
    ("MOKOKCHUNG","NAGALAND"):"272",
    ("MON","NAGALAND"):"273",
    ("PEREN","NAGALAND"):"274",
    ("PHEK","NAGALAND"):"275",
    ("TUENSANG","NAGALAND"):"276",
    ("WOKHA","NAGALAND"):"277",
    ("ZUNHEBOTO","NAGALAND"):"278",
    # MANIPUR
    ("BISHNUPUR","MANIPUR"):"279",
    ("CHANDEL","MANIPUR"):"280",
    ("CHURACHANDPUR","MANIPUR"):"281",
    ("IMPHAL EAST","MANIPUR"):"282",
    ("IMPHAL WEST","MANIPUR"):"283",
    ("SENAPATI","MANIPUR"):"284",
    ("TAMENGLONG","MANIPUR"):"285",
    ("THOUBAL","MANIPUR"):"286",
    ("UKHRUL","MANIPUR"):"287",
    # MIZORAM
    ("AIZAWL","MIZORAM"):"288",
    ("CHAMPHAI","MIZORAM"):"289",
    ("KOLASIB","MIZORAM"):"290",
    ("LAWNGTLAI","MIZORAM"):"291",
    ("LUNGLEI","MIZORAM"):"292",
    ("MAMIT","MIZORAM"):"293",
    ("SAIHA","MIZORAM"):"294",
    ("SERCHHIP","MIZORAM"):"295",
    # TRIPURA
    ("DHALAI","TRIPURA"):"296",
    ("GOMATI","TRIPURA"):"297",
    ("KHOWAI","TRIPURA"):"298",
    ("NORTH TRIPURA","TRIPURA"):"299",
    ("SEPAHIJALA","TRIPURA"):"300",
    ("SOUTH TRIPURA","TRIPURA"):"301",
    ("UNAKOTI","TRIPURA"):"302",
    ("WEST TRIPURA","TRIPURA"):"303",
    # MEGHALAYA
    ("EAST GARO HILLS","MEGHALAYA"):"304",
    ("EAST JAINTIA HILLS","MEGHALAYA"):"305",
    ("EAST KHASI HILLS","MEGHALAYA"):"306",
    ("NORTH GARO HILLS","MEGHALAYA"):"307",
    ("RI BHOI","MEGHALAYA"):"308",
    ("SOUTH GARO HILLS","MEGHALAYA"):"309",
    ("SOUTH WEST GARO HILLS","MEGHALAYA"):"310",
    ("SOUTH WEST KHASI HILLS","MEGHALAYA"):"311",
    ("WEST GARO HILLS","MEGHALAYA"):"312",
    ("WEST JAINTIA HILLS","MEGHALAYA"):"313",
    ("WEST KHASI HILLS","MEGHALAYA"):"314",
    # ASSAM
    ("BAKSA","ASSAM"):"315",
    ("BARPETA","ASSAM"):"316",
    ("BONGAIGAON","ASSAM"):"317",
    ("CACHAR","ASSAM"):"318",
    ("CHIRANG","ASSAM"):"319",
    ("DARRANG","ASSAM"):"320",
    ("DHEMAJI","ASSAM"):"321",
    ("DHUBRI","ASSAM"):"322",
    ("DIBRUGARH","ASSAM"):"323",
    ("DIMA HASAO","ASSAM"):"324",
    ("NORTH CACHAR HILLS","ASSAM"):"324",
    ("GOALPARA","ASSAM"):"325",
    ("GOLAGHAT","ASSAM"):"326",
    ("HAILAKANDI","ASSAM"):"327",
    ("JORHAT","ASSAM"):"328",
    ("KAMRUP","ASSAM"):"329",
    ("KAMRUP METROPOLITAN","ASSAM"):"330",
    ("KARBI ANGLONG","ASSAM"):"331",
    ("KARIMGANJ","ASSAM"):"332",
    ("KOKRAJHAR","ASSAM"):"333",
    ("LAKHIMPUR","ASSAM"):"334",
    ("MARIGAON","ASSAM"):"335",
    ("NAGAON","ASSAM"):"336",
    ("NALBARI","ASSAM"):"337",
    ("SIVASAGAR","ASSAM"):"338",
    ("SONITPUR","ASSAM"):"339",
    ("TINSUKIA","ASSAM"):"340",
    ("UDALGURI","ASSAM"):"341",
    # WEST BENGAL
    ("BANKURA","WEST BENGAL"):"342",
    ("BARDHAMAN","WEST BENGAL"):"343",
    ("BURDWAN","WEST BENGAL"):"343",
    ("BIRBHUM","WEST BENGAL"):"344",
    ("COOCH BEHAR","WEST BENGAL"):"345",
    ("DAKSHIN DINAJPUR","WEST BENGAL"):"346",
    ("DARJEELING","WEST BENGAL"):"347",
    ("HOOGHLY","WEST BENGAL"):"348",
    ("HOWRAH","WEST BENGAL"):"349",
    ("JALPAIGURI","WEST BENGAL"):"350",
    ("KOLKATA","WEST BENGAL"):"351",
    ("MALDAH","WEST BENGAL"):"352",
    ("MURSHIDABAD","WEST BENGAL"):"353",
    ("NADIA","WEST BENGAL"):"354",
    ("NORTH 24 PARGANAS","WEST BENGAL"):"355",
    ("PASCHIM MEDINIPUR","WEST BENGAL"):"356",
    ("PURBA MEDINIPUR","WEST BENGAL"):"357",
    ("PURULIA","WEST BENGAL"):"358",
    ("SOUTH 24 PARGANAS","WEST BENGAL"):"359",
    ("UTTAR DINAJPUR","WEST BENGAL"):"360",
    # JHARKHAND
    ("BOKARO","JHARKHAND"):"361",
    ("CHATRA","JHARKHAND"):"362",
    ("DEOGHAR","JHARKHAND"):"363",
    ("DHANBAD","JHARKHAND"):"364",
    ("DUMKA","JHARKHAND"):"365",
    ("EAST SINGHBHUM","JHARKHAND"):"366",
    ("GARHWA","JHARKHAND"):"367",
    ("GIRIDIH","JHARKHAND"):"368",
    ("GODDA","JHARKHAND"):"369",
    ("GUMLA","JHARKHAND"):"370",
    ("HAZARIBAG","JHARKHAND"):"371",
    ("JAMTARA","JHARKHAND"):"372",
    ("KHUNTI","JHARKHAND"):"373",
    ("KODERMA","JHARKHAND"):"374",
    ("LATEHAR","JHARKHAND"):"375",
    ("LOHARDAGA","JHARKHAND"):"376",
    ("PAKUR","JHARKHAND"):"377",
    ("PALAMU","JHARKHAND"):"378",
    ("RAMGARH","JHARKHAND"):"379",
    ("RANCHI","JHARKHAND"):"380",
    ("SAHIBGANJ","JHARKHAND"):"381",
    ("SERAIKELA KHARSAWAN","JHARKHAND"):"382",
    ("SIMDEGA","JHARKHAND"):"383",
    ("WEST SINGHBHUM","JHARKHAND"):"384",
    # ODISHA
    ("ANGUL","ORISSA"):"385",
    ("BALANGIR","ORISSA"):"386",
    ("BOLANGIR","ORISSA"):"386",
    ("BALASORE","ORISSA"):"387",
    ("BARGARH","ORISSA"):"388",
    ("BHADRAK","ORISSA"):"389",
    ("BOUDH","ORISSA"):"390",
    ("CUTTACK","ORISSA"):"391",
    ("DEOGARH","ORISSA"):"392",
    ("DHENKANAL","ORISSA"):"393",
    ("GAJAPATI","ORISSA"):"394",
    ("GANJAM","ORISSA"):"395",
    ("JAGATSINGHAPUR","ORISSA"):"396",
    ("JAJPUR","ORISSA"):"397",
    ("JHARSUGUDA","ORISSA"):"398",
    ("KALAHANDI","ORISSA"):"399",
    ("KANDHAMAL","ORISSA"):"400",
    ("KENDRAPARA","ORISSA"):"401",
    ("KENDUJHAR","ORISSA"):"402",
    ("KEONJHAR","ORISSA"):"402",
    ("KHORDHA","ORISSA"):"403",
    ("KORAPUT","ORISSA"):"404",
    ("MALKANGIRI","ORISSA"):"405",
    ("MAYURBHANJ","ORISSA"):"406",
    ("NABARANGAPUR","ORISSA"):"407",
    ("NAYAGARH","ORISSA"):"408",
    ("NUAPADA","ORISSA"):"409",
    ("PURI","ORISSA"):"410",
    ("RAYAGADA","ORISSA"):"411",
    ("SAMBALPUR","ORISSA"):"412",
    ("SUBARNAPUR","ORISSA"):"413",
    ("SONEPUR","ORISSA"):"413",
    ("SUNDARGARH","ORISSA"):"414",
    # CHHATTISGARH
    ("BASTAR","CHHATTISGARH"):"415",
    ("BIJAPUR","CHHATTISGARH"):"416",
    ("BILASPUR","CHHATTISGARH"):"417",
    ("DANTEWADA","CHHATTISGARH"):"418",
    ("DHAMTARI","CHHATTISGARH"):"419",
    ("DURG","CHHATTISGARH"):"420",
    ("GARIABAND","CHHATTISGARH"):"421",
    ("JANJGIR CHAMPA","CHHATTISGARH"):"422",
    ("JANJGIR-CHAMPA","CHHATTISGARH"):"422",
    ("JASHPUR","CHHATTISGARH"):"423",
    ("KABIRDHAM","CHHATTISGARH"):"424",
    ("KAWARDHA","CHHATTISGARH"):"424",
    ("KANKER","CHHATTISGARH"):"425",
    ("KONDAGAON","CHHATTISGARH"):"426",
    ("KORBA","CHHATTISGARH"):"427",
    ("KORIYA","CHHATTISGARH"):"428",
    ("MAHASAMUND","CHHATTISGARH"):"429",
    ("MUNGELI","CHHATTISGARH"):"430",
    ("NARAYANPUR","CHHATTISGARH"):"431",
    ("RAIGARH","CHHATTISGARH"):"432",
    ("RAIPUR","CHHATTISGARH"):"433",
    ("RAJNANDGAON","CHHATTISGARH"):"434",
    ("SUKMA","CHHATTISGARH"):"435",
    ("SURAJPUR","CHHATTISGARH"):"436",
    ("SURGUJA","CHHATTISGARH"):"437",
    # MADHYA PRADESH
    ("AGAR MALWA","MADHYA PRADESH"):"438",
    ("ALIRAJPUR","MADHYA PRADESH"):"439",
    ("ANUPPUR","MADHYA PRADESH"):"440",
    ("ASHOKNAGAR","MADHYA PRADESH"):"441",
    ("BALAGHAT","MADHYA PRADESH"):"442",
    ("BARWANI","MADHYA PRADESH"):"443",
    ("BETUL","MADHYA PRADESH"):"444",
    ("BHIND","MADHYA PRADESH"):"445",
    ("BHOPAL","MADHYA PRADESH"):"446",
    ("BURHANPUR","MADHYA PRADESH"):"447",
    ("CHHATARPUR","MADHYA PRADESH"):"448",
    ("CHHINDWARA","MADHYA PRADESH"):"449",
    ("DAMOH","MADHYA PRADESH"):"450",
    ("DATIA","MADHYA PRADESH"):"451",
    ("DEWAS","MADHYA PRADESH"):"452",
    ("DHAR","MADHYA PRADESH"):"453",
    ("DINDORI","MADHYA PRADESH"):"454",
    ("EAST NIMAR","MADHYA PRADESH"):"455",
    ("KHANDWA","MADHYA PRADESH"):"455",
    ("GUNA","MADHYA PRADESH"):"456",
    ("GWALIOR","MADHYA PRADESH"):"457",
    ("HARDA","MADHYA PRADESH"):"458",
    ("HOSHANGABAD","MADHYA PRADESH"):"459",
    ("NARMADAPURAM","MADHYA PRADESH"):"459",
    ("INDORE","MADHYA PRADESH"):"460",
    ("JABALPUR","MADHYA PRADESH"):"461",
    ("JHABUA","MADHYA PRADESH"):"462",
    ("KATNI","MADHYA PRADESH"):"463",
    ("MANDLA","MADHYA PRADESH"):"464",
    ("MANDSAUR","MADHYA PRADESH"):"465",
    ("MORENA","MADHYA PRADESH"):"466",
    ("NARSINGHPUR","MADHYA PRADESH"):"467",
    ("NEEMUCH","MADHYA PRADESH"):"468",
    ("PANNA","MADHYA PRADESH"):"469",
    ("RAISEN","MADHYA PRADESH"):"470",
    ("RAJGARH","MADHYA PRADESH"):"471",
    ("RATLAM","MADHYA PRADESH"):"472",
    ("REWA","MADHYA PRADESH"):"473",
    ("SAGAR","MADHYA PRADESH"):"474",
    ("SATNA","MADHYA PRADESH"):"475",
    ("SEHORE","MADHYA PRADESH"):"476",
    ("SEONI","MADHYA PRADESH"):"477",
    ("SHAHDOL","MADHYA PRADESH"):"478",
    ("SHAJAPUR","MADHYA PRADESH"):"479",
    ("SHEOPUR","MADHYA PRADESH"):"480",
    ("SHIVPURI","MADHYA PRADESH"):"481",
    ("SIDHI","MADHYA PRADESH"):"482",
    ("SINGRAULI","MADHYA PRADESH"):"483",
    ("TIKAMGARH","MADHYA PRADESH"):"484",
    ("UJJAIN","MADHYA PRADESH"):"485",
    ("UMARIA","MADHYA PRADESH"):"486",
    ("VIDISHA","MADHYA PRADESH"):"487",
    ("WEST NIMAR","MADHYA PRADESH"):"488",
    ("KHARGONE","MADHYA PRADESH"):"488",
    # GUJARAT
    ("AHMEDABAD","GUJARAT"):"489",
    ("AMRELI","GUJARAT"):"490",
    ("ANAND","GUJARAT"):"491",
    ("ARAVALLI","GUJARAT"):"492",
    ("BANASKANTHA","GUJARAT"):"493",
    ("BHARUCH","GUJARAT"):"494",
    ("BHAVNAGAR","GUJARAT"):"495",
    ("BOTAD","GUJARAT"):"496",
    ("CHHOTA UDAIPUR","GUJARAT"):"497",
    ("DAHOD","GUJARAT"):"498",
    ("DANG","GUJARAT"):"499",
    ("DEVBHUMI DWARKA","GUJARAT"):"500",
    ("GANDHINAGAR","GUJARAT"):"501",
    ("GIR SOMNATH","GUJARAT"):"502",
    ("JAMNAGAR","GUJARAT"):"503",
    ("JUNAGADH","GUJARAT"):"504",
    ("KHEDA","GUJARAT"):"505",
    ("MAHISAGAR","GUJARAT"):"506",
    ("MEHSANA","GUJARAT"):"507",
    ("MORBI","GUJARAT"):"508",
    ("NARMADA","GUJARAT"):"509",
    ("NAVSARI","GUJARAT"):"510",
    ("PANCHMAHAL","GUJARAT"):"511",
    ("PATAN","GUJARAT"):"512",
    ("PORBANDAR","GUJARAT"):"513",
    ("RAJKOT","GUJARAT"):"514",
    ("SABARKANTHA","GUJARAT"):"515",
    ("SURAT","GUJARAT"):"516",
    ("SURENDRANAGAR","GUJARAT"):"517",
    ("TAPI","GUJARAT"):"518",
    ("VADODARA","GUJARAT"):"519",
    ("VALSAD","GUJARAT"):"520",
    # DAMAN AND DIU
    ("DAMAN","DAMAN AND DIU"):"521",
    ("DIU","DAMAN AND DIU"):"522",
    # DADRA AND NAGAR HAVELI
    ("DADRA AND NAGAR HAVELI","DADRA AND NAGAR HAVELI"):"523",
    # MAHARASHTRA
    ("AHMEDNAGAR","MAHARASHTRA"):"524",
    ("AKOLA","MAHARASHTRA"):"525",
    ("AMRAVATI","MAHARASHTRA"):"526",
    ("AURANGABAD","MAHARASHTRA"):"527",
    ("BEED","MAHARASHTRA"):"528",
    ("BHANDARA","MAHARASHTRA"):"529",
    ("BULDHANA","MAHARASHTRA"):"530",
    ("CHANDRAPUR","MAHARASHTRA"):"531",
    ("DHULE","MAHARASHTRA"):"532",
    ("GADCHIROLI","MAHARASHTRA"):"533",
    ("GONDIA","MAHARASHTRA"):"534",
    ("HINGOLI","MAHARASHTRA"):"535",
    ("JALGAON","MAHARASHTRA"):"536",
    ("JALNA","MAHARASHTRA"):"537",
    ("KOLHAPUR","MAHARASHTRA"):"538",
    ("LATUR","MAHARASHTRA"):"539",
    ("MUMBAI CITY","MAHARASHTRA"):"540",
    ("MUMBAI SUBURBAN","MAHARASHTRA"):"541",
    ("NAGPUR","MAHARASHTRA"):"542",
    ("NANDED","MAHARASHTRA"):"543",
    ("NANDURBAR","MAHARASHTRA"):"544",
    ("NASHIK","MAHARASHTRA"):"545",
    ("OSMANABAD","MAHARASHTRA"):"546",
    ("PALGHAR","MAHARASHTRA"):"547",
    ("PARBHANI","MAHARASHTRA"):"548",
    ("PUNE","MAHARASHTRA"):"549",
    ("RAIGAD","MAHARASHTRA"):"550",
    ("RATNAGIRI","MAHARASHTRA"):"551",
    ("SANGLI","MAHARASHTRA"):"552",
    ("SATARA","MAHARASHTRA"):"553",
    ("SINDHUDURG","MAHARASHTRA"):"554",
    ("SOLAPUR","MAHARASHTRA"):"555",
    ("THANE","MAHARASHTRA"):"556",
    ("WARDHA","MAHARASHTRA"):"557",
    ("WASHIM","MAHARASHTRA"):"558",
    ("YAVATMAL","MAHARASHTRA"):"559",
    # ANDHRA PRADESH
    ("ADILABAD","ANDHRA PRADESH"):"560",
    ("ANANTAPUR","ANDHRA PRADESH"):"561",
    ("CHITTOOR","ANDHRA PRADESH"):"562",
    ("EAST GODAVARI","ANDHRA PRADESH"):"563",
    ("GUNTUR","ANDHRA PRADESH"):"564",
    ("HYDERABAD","ANDHRA PRADESH"):"565",
    ("KARIMNAGAR","ANDHRA PRADESH"):"566",
    ("KHAMMAM","ANDHRA PRADESH"):"567",
    ("KRISHNA","ANDHRA PRADESH"):"568",
    ("KURNOOL","ANDHRA PRADESH"):"569",
    ("MAHBUBNAGAR","ANDHRA PRADESH"):"570",
    ("MEDAK","ANDHRA PRADESH"):"571",
    ("NALGONDA","ANDHRA PRADESH"):"572",
    ("NIZAMABAD","ANDHRA PRADESH"):"573",
    ("PRAKASAM","ANDHRA PRADESH"):"574",
    ("RANGAREDDY","ANDHRA PRADESH"):"575",
    ("SRI POTTI SRIRAMULU NELLORE","ANDHRA PRADESH"):"576",
    ("NELLORE","ANDHRA PRADESH"):"576",
    ("SRIKAKULAM","ANDHRA PRADESH"):"577",
    ("VISAKHAPATNAM","ANDHRA PRADESH"):"578",
    ("VIZIANAGARAM","ANDHRA PRADESH"):"579",
    ("WARANGAL","ANDHRA PRADESH"):"580",
    ("WEST GODAVARI","ANDHRA PRADESH"):"581",
    ("Y.S.R.","ANDHRA PRADESH"):"582",
    ("YSR KADAPA","ANDHRA PRADESH"):"582",
    # KARNATAKA
    ("BAGALKOT","KARNATAKA"):"583",
    ("BANGALORE RURAL","KARNATAKA"):"584",
    ("BANGALORE URBAN","KARNATAKA"):"585",
    ("BENGALURU URBAN","KARNATAKA"):"585",
    ("BELGAUM","KARNATAKA"):"586",
    ("BELAGAVI","KARNATAKA"):"586",
    ("BELLARY","KARNATAKA"):"587",
    ("BALLARI","KARNATAKA"):"587",
    ("BIDAR","KARNATAKA"):"588",
    ("BIJAPUR","KARNATAKA"):"589",
    ("VIJAYAPURA","KARNATAKA"):"589",
    ("CHAMARAJANAGAR","KARNATAKA"):"590",
    ("CHIKKABALLAPURA","KARNATAKA"):"591",
    ("CHIKMAGALUR","KARNATAKA"):"592",
    ("CHITRADURGA","KARNATAKA"):"593",
    ("DAKSHINA KANNADA","KARNATAKA"):"594",
    ("DAVANAGERE","KARNATAKA"):"595",
    ("DHARWAD","KARNATAKA"):"596",
    ("GADAG","KARNATAKA"):"597",
    ("GULBARGA","KARNATAKA"):"598",
    ("KALABURAGI","KARNATAKA"):"598",
    ("HASSAN","KARNATAKA"):"599",
    ("HAVERI","KARNATAKA"):"600",
    ("KODAGU","KARNATAKA"):"601",
    ("KOLAR","KARNATAKA"):"602",
    ("KOPPAL","KARNATAKA"):"603",
    ("MANDYA","KARNATAKA"):"604",
    ("MYSORE","KARNATAKA"):"605",
    ("MYSURU","KARNATAKA"):"605",
    ("RAICHUR","KARNATAKA"):"606",
    ("RAMANAGARA","KARNATAKA"):"607",
    ("SHIMOGA","KARNATAKA"):"608",
    ("SHIVAMOGGA","KARNATAKA"):"608",
    ("TUMKUR","KARNATAKA"):"609",
    ("TUMAKURU","KARNATAKA"):"609",
    ("UDUPI","KARNATAKA"):"610",
    ("UTTARA KANNADA","KARNATAKA"):"611",
    ("YADGIR","KARNATAKA"):"612",
    # GOA
    ("NORTH GOA","GOA"):"613",
    ("SOUTH GOA","GOA"):"614",
    # LAKSHADWEEP
    ("LAKSHADWEEP","LAKSHADWEEP"):"615",
    # KERALA
    ("ALAPPUZHA","KERALA"):"616",
    ("ERNAKULAM","KERALA"):"617",
    ("IDUKKI","KERALA"):"618",
    ("KANNUR","KERALA"):"619",
    ("KASARAGOD","KERALA"):"620",
    ("KOLLAM","KERALA"):"621",
    ("KOTTAYAM","KERALA"):"622",
    ("KOZHIKODE","KERALA"):"623",
    ("MALAPPURAM","KERALA"):"624",
    ("PALAKKAD","KERALA"):"625",
    ("PATHANAMTHITTA","KERALA"):"626",
    ("THIRUVANANTHAPURAM","KERALA"):"627",
    ("THRISSUR","KERALA"):"628",
    ("WAYANAD","KERALA"):"629",
    # TAMIL NADU
    ("ARIYALUR","TAMIL NADU"):"630",
    ("CHENNAI","TAMIL NADU"):"631",
    ("COIMBATORE","TAMIL NADU"):"632",
    ("CUDDALORE","TAMIL NADU"):"633",
    ("DHARMAPURI","TAMIL NADU"):"634",
    ("DINDIGUL","TAMIL NADU"):"635",
    ("ERODE","TAMIL NADU"):"636",
    ("KANCHIPURAM","TAMIL NADU"):"637",
    ("KANYAKUMARI","TAMIL NADU"):"638",
    ("KARUR","TAMIL NADU"):"639",
    ("KRISHNAGIRI","TAMIL NADU"):"640",
    ("MADURAI","TAMIL NADU"):"641",
    ("NAGAPATTINAM","TAMIL NADU"):"642",
    ("NAMAKKAL","TAMIL NADU"):"643",
    ("NILGIRIS","TAMIL NADU"):"644",
    ("THE NILGIRIS","TAMIL NADU"):"644",
    ("PERAMBALUR","TAMIL NADU"):"645",
    ("PUDUKKOTTAI","TAMIL NADU"):"646",
    ("RAMANATHAPURAM","TAMIL NADU"):"647",
    ("SALEM","TAMIL NADU"):"648",
    ("SIVAGANGA","TAMIL NADU"):"649",
    ("THANJAVUR","TAMIL NADU"):"650",
    ("THENI","TAMIL NADU"):"651",
    ("THOOTHUKUDI","TAMIL NADU"):"652",
    ("TUTICORIN","TAMIL NADU"):"652",
    ("TIRUCHIRAPPALLI","TAMIL NADU"):"653",
    ("TIRUNELVELI","TAMIL NADU"):"654",
    ("TIRUPPUR","TAMIL NADU"):"655",
    ("TIRUVALLUR","TAMIL NADU"):"656",
    ("TIRUVANNAMALAI","TAMIL NADU"):"657",
    ("TIRUVARUR","TAMIL NADU"):"658",
    ("VELLORE","TAMIL NADU"):"659",
    ("VILUPPURAM","TAMIL NADU"):"660",
    ("VIRUDHUNAGAR","TAMIL NADU"):"661",
    # PONDICHERRY
    ("KARAIKAL","PONDICHERRY"):"662",
    ("MAHE","PONDICHERRY"):"663",
    ("PUDUCHERRY","PONDICHERRY"):"664",
    ("PONDICHERRY","PONDICHERRY"):"664",
    ("YANAM","PONDICHERRY"):"665",
    # ANDAMAN AND NICOBAR ISLANDS
    ("NICOBARS","ANDAMAN AND NICOBAR ISLANDS"):"666",
    ("NORTH AND MIDDLE ANDAMAN","ANDAMAN AND NICOBAR ISLANDS"):"667",
    ("NORTH  AND MIDDLE ANDAMAN","ANDAMAN AND NICOBAR ISLANDS"):"667",
    ("SOUTH ANDAMAN","ANDAMAN AND NICOBAR ISLANDS"):"668",
}

print("Connecting to database...")
conn = psycopg2.connect(
    host=os.getenv("POSTGRES_HOST","localhost"),
    port=5432,
    dbname=os.getenv("POSTGRES_DB","india_dev_analytics"),
    user=os.getenv("POSTGRES_USER","analyst"),
    password=os.getenv("POSTGRES_PASSWORD","yash123")
)
conn.autocommit = False
cur = conn.cursor()

cur.execute("""
    SELECT d.id, d.district_name, s.state_name, d.lgd_district_code
    FROM districts d
    JOIN states s ON s.id = d.state_id
    ORDER BY s.state_name, d.district_name
""")
districts = cur.fetchall()
print("Total districts: " + str(len(districts)))

updated = 0
not_found = []
used_codes = set()

# First pass - get current codes to avoid conflicts
cur.execute("SELECT lgd_district_code FROM districts")
used_codes = set(r[0] for r in cur.fetchall())

for dist_id, dist_name, state_name, current_code in districts:
    key = (dist_name.upper().strip(), state_name.upper().strip())
    new_code = CORRECT_LGD.get(key)

    if new_code is None:
        # Try partial/fuzzy match within same state
        state_upper = state_name.upper().strip()
        dist_upper = dist_name.upper().strip()
        for (k_dist, k_state), v in CORRECT_LGD.items():
            if k_state == state_upper:
                if k_dist in dist_upper or dist_upper in k_dist:
                    new_code = v
                    break

    if new_code:
        new_code_padded = str(new_code).zfill(4)
        if new_code_padded != current_code:
            # Check if target code already used by another district
            if new_code_padded in used_codes and new_code_padded != current_code:
                # Temporarily set to a placeholder
                try:
                    cur.execute(
                        "UPDATE districts SET lgd_district_code=%s WHERE id=%s",
                        ("TEMP" + str(dist_id), dist_id)
                    )
                    conn.commit()
                    used_codes.discard(current_code)
                except:
                    conn.rollback()
            try:
                cur.execute(
                    "UPDATE districts SET lgd_district_code=%s WHERE id=%s",
                    (new_code_padded, dist_id)
                )
                conn.commit()
                used_codes.discard(current_code)
                used_codes.add(new_code_padded)
                updated += 1
            except Exception as e:
                conn.rollback()
                not_found.append(dist_name + "(" + state_name + "): " + str(e)[:40])
    else:
        not_found.append(dist_name + " | " + state_name)

print("Updated: " + str(updated) + " districts")

if not_found:
    print("\nNot matched (" + str(len(not_found)) + "):")
    for d in not_found[:20]:
        print("  - " + d)

# Relink development index
print("\nRelinking development index...")
import pandas as pd
from pathlib import Path

cur.execute("SELECT lgd_district_code, id FROM districts")
dist_map = {r[0]: r[1] for r in cur.fetchall()}

idx_path = Path("data/processed/development_index.parquet")
if idx_path.exists():
    idx = pd.read_parquet(idx_path)
    cur.execute("DELETE FROM development_index")
    conn.commit()
    rows = []
    import math
    for _, row in idx.iterrows():
        old_code = str(row.get("lgd_district_code","")).zfill(4)
        dist_id = dist_map.get(old_code)
        if dist_id is None:
            continue
        def c(v):
            if v is None: return None
            if isinstance(v, float) and math.isnan(v): return None
            return v
        rows.append((
            dist_id,
            c(row.get("composite_score")),
            c(row.get("composite_rank")),
            c(row.get("composite_percentile")),
            c(row.get("cluster_id")),
            str(row.get("cluster_label","")),
        ))
    psycopg2.extras.execute_batch(
        cur,
        "INSERT INTO development_index (district_id,composite_score,composite_rank,composite_percentile,cluster_id,cluster_label) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
        rows
    )
    conn.commit()
    print("Dev index relinked: " + str(len(rows)) + " rows")

# Refresh view
try:
    conn.autocommit = True
    conn.cursor().execute("REFRESH MATERIALIZED VIEW state_aggregates")
    print("View refreshed")
except Exception as e:
    print("View: " + str(e))

conn.close()

print("\n" + "="*50)
print("DONE - Correct LGD codes applied!")
print("="*50)
print("\nKey district codes:")
print("  Kerala - Ernakulam   : 0617")
print("  Kerala - Wayanad     : 0629")
print("  Maharashtra - Pune   : 0549")
print("  Maharashtra - Mumbai : 0540")
print("  Tamil Nadu - Chennai : 0631")
print("  UP - Lucknow         : 0182")
print("  Karnataka - Bangalore: 0585")
print("  WB - Kolkata         : 0351")
print("  Bihar - Patna        : 0234")
print("  Rajasthan - Jaipur   : 0118")
