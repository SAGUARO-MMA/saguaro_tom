from enum import Enum

from astropy.table import Table

Catalogs = Enum('Catalogs', [
    ('DESI_DR1', 'DESIDR1'),
    ('Fermi_LPSC', 'FERMILPSC'),
    ('NEDLVS', 'NEDLVS')
])

def get_prepped_catalog(source_path: str, catalog_type: str) -> Table:
    match Catalogs[catalog_type]:
        case Catalogs.DESI_DR1:
            return DESIDR1Config(source_path).get_table()
        case Catalogs.Fermi_LPSC:
            return FermiLPSCConfig(source_path).get_table()
        case Catalogs.NEDLVS:
            return NEDLVSConfig(source_path).get_table()
        case _:
            raise ValueError("Invalid Catalog Type Specified")

class CatalogConfig():
    data_table = None

    def __init__(self, path: str):
        # ex: self.table = FermilpscConfig._open_file(path)
        # ex: self.table = self._process_table(self.table)
        raise NotImplementedError('No implementation for __init__()')

    @staticmethod
    def _open_file(self, path: str) -> Table:
        # ex: return Table.read(path)
        raise NotImplementedError('No implementation for open_file()')
    
    def _clean_table(self) -> Table:
        # TODO: separate processing against whole table vs chunks

        # ex: self.table.keep_columns(['ra', 'dec']) # modifies in place
        # ex: self.table['ra'] *= 3.141592653589793 / 180 # just an ex, idk if anyone will use rads
        # ex: self.table['ra'].name = 'ra_rads'
        # ex: self.table['redshift'].name = 'red_shift'
        raise NotImplementedError('No implementation for process_table()')
    
    def get_table(self) -> Table:
        # ex: return self.table
        raise NotImplementedError('No implementation for get_table()')
    
class DESIDR1Config(CatalogConfig):
    def __init__(self, path: str):
        self.table = DESIDR1Config._open_file(path)
        self.table = self._clean_table(self.table)

    @staticmethod
    def _open_file(path):
        return Table.read(path)

    def _clean_table(self, new_table) -> Table:
        return new_table # no modifications to table are necessary
    
    def get_table(self):
        return self.table


class FermiLPSCConfig(CatalogConfig):
    def __init__(self, path: str):
        self.table = FermiLPSCConfig._open_file(path)
        self.table = self._clean_table(self.table)

    @staticmethod
    def _open_file(path):
        return Table.read(path)

    def _clean_table(self, new_table) -> Table:
        return new_table # no modifications to table are necessary
    
    def get_table(self):
        return self.table

class NEDLVSConfig(CatalogConfig):
    def __init__(self, path: str):
        self.table = NEDLVSConfig._open_file(path)
        self.table = self._clean_table(self.table)

    @staticmethod
    def _open_file(path):
        return Table.read(path)

    def _clean_table(self, new_table) -> Table:
        return new_table # no modifications to table are necessary
    
    def get_table(self):
        return self.table

