import adif_io
from pyhamtools import LookupLib, Callinfo

my_lookuplib = LookupLib(lookuptype="countryfile")
cic = Callinfo(my_lookuplib)

def get_unique_adif_ids(adif_file_path):
    """
    Reads an ADIF file and returns a set of unique 'adif_id' fields.

    :param adif_file_path: Path to the ADIF file.
    :return: Set of unique adif_id values.
    """

    calls_set = set()
    list_of_adif_ids = set()

    adif_data, _ = adif_io.read_from_file(adif_file_path)
    
    for record in adif_data:
        calls_set.add(record['CALL'])

    for call in calls_set:
        callinfo = cic.get_all(call)
        list_of_adif_ids.add(callinfo['adif'])
        
    return list_of_adif_ids

adifs_set = get_unique_adif_ids("lotwreport.adi")
print(f"{len(adifs_set)} found")
print(adifs_set)