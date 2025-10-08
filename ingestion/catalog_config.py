import astropy

class CatalogConfig():
    data_table = None

    def __init__(self, path: str):
        raise NotImplementedError('No implementation for __init__()')

    def _open_file(self, path: str):
        raise NotImplementedError('No implementation for open_file()')
    
    def _process_table(self):
        raise NotImplementedError('No implementation for process_table()')
    
    def get_table(self) -> astropy.table.table.Table:
        raise NotImplementedError('No implementation for get_table()')
    
