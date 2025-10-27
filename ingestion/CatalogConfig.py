from enum import Enum
import logging

from astropy.table import Table
import psycopg

from ingest_extras import *
import numpy2PGSQL

logger = logging.getLogger(__name__)

Catalogs = Enum('Catalogs', 
[
    ('DESI_DR1', 'DESIDR1'),
    ('Fermi_LPSC', 'FERMILPSC'),
    ('Fermi_3FHL', 'FERMI3FHL'),
    ('NEDLVS', 'NEDLVS')
])

class CatalogConfig():
    def __init__(self, dbctxt: DBctxt, path: str):
        self.dbctxt:            DBctxt = dbctxt
        self.path:              str    = path
        self.relational_schema: str    = None

    # ##########################################################################
    # "private"
    # ##########################################################################
    def _tabularize(self, path: str):
        # ex: return Table.read(path)
        raise NotImplementedError()
    
    def _clean_table(self):
        # TODO: separate processing against whole table vs chunks

        # ex: self.table.keep_columns(['ra', 'dec']) # modifies in place
        # ex: self.table['ra'] *= 3.141592653589793 / 180 # just an ex, idk if anyone will use rads
        # ex: self.table['ra'].name = 'ra_rads'
        # ex: self.table['redshift'].name = 'red_shift'
        raise NotImplementedError()
    
    def _relational_schema(self):
        raise NotImplementedError()

    def _create_table(self):
        raise NotImplementedError

    def _data2SQLValue(self) -> str:
        raise NotImplementedError()

    # def insert(self, vals: str)

    # ##########################################################################
    # "public"
    # ##########################################################################
    def insert_all(self):
        raise NotImplementedError()

class BasicAstropyConfig(CatalogConfig):
    def __init__(self, dbctxt: DBctxt, path: str, chunk_rows: int = 100000):
        super().__init__(dbctxt, path)

        self.chunk_rows: int = int(chunk_rows)

        BasicAstropyConfig._tabularize(self, path)
        BasicAstropyConfig._clean_table(self)
        BasicAstropyConfig._relational_schema(self)

    def _tabularize(self, path):
        self.table = Table.read(path)

    def _clean_table(self):
        pass # no modifications to table are necessary

    def _relational_schema(self):
            self.relational_schema = "( "

            # ap_types = set() # used in devel to get src data types (in the fits file, not implementation)
            for col_index in range(len(self.table.colnames)):
                colname = self.table.colnames[col_index]
                np_dtype = str(type(self.table[colname][0]))
                ap_dtype = self.table[self.table.colnames[col_index]].dtype.str
                pg_type = numpy2PGSQL.convert(ap_dtype)
                
                # ap_types.add(ap_dtype) # used in devel to get src data types (in the fits file, not implementation)
                self.relational_schema += f"\n{colname.ljust(20)}\t{pg_type},"
        
            self.relational_schema = self.relational_schema[:-1] # get rid of the trailing comma bc PGSQL syntax won't ignore it
            self.relational_schema += ")"
            # print(ap_types) # used in devel to get src data types (in the fits file, not implementation)
            return self.relational_schema

    def _create_table(self):
        # #####################################################################
        # TODO: drop table & create new, edit in place?
        # #####################################################################
        logger.info(f"Creating new table in database {self.dbctxt.POSTGRES_DB} on host {self.dbctxt.POSTGRES_HOST}.")

        SQL_statement = ""
        
        SQL_statement += f"DROP TABLE IF EXISTS {self.dbctxt.sql_table};\n"
        
        SQL_statement += f"CREATE TABLE {self.dbctxt.sql_table} {self.relational_schema};"
        with psycopg.connect(host=self.dbctxt.POSTGRES_HOST, port=self.dbctxt.POSTGRES_PORT, dbname=self.dbctxt.POSTGRES_DB, user=self.dbctxt.POSTGRES_USER, password=self.dbctxt.POSTGRES_PASSWORD) as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(SQL_statement)
                    conn.commit()
                except psycopg.errors.DuplicateTable:
                    raise f"Table {self.dbctxt.sql_table} already exists. Attemtping to continue with existing schema..."
                except Exception as e: raise

        logger.info("done creating table.")
                
    def _data2SQLValue(self, rows: range) -> str:
        all_values = []
    
        cols = range(len(self.table.columns))

        for row_index in rows:
            values = "( "
            for col_index in cols:
                value = str(self.table[row_index][col_index])
                valtype = numpy2PGSQL.convert(self.table[self.table.colnames[col_index]].dtype.str)

                # #####################################################################
                # TODO: make a more comprehensive, flexible fun. for cleaning
                # #####################################################################
                if value == "--":
                        value = "null"

                if valtype == "text":
                    value = value.replace('"', '"""') # SQL escapes a quote with another quote
                    value = value.replace("'", "''")
                    values += f"\'{value}\', "
                else:
                    values += f"{value}, "

            values = values[:-2] # strip trailing comma bc PGSQL syntax won't accept it
            values += " )"

            all_values.append(values)

        return all_values
    
    def insert_all(self):
        self._create_table()
        
        for i in range(0, len(self.table), self.chunk_rows):

            stringified_chunk = ""
            SQL_statement = ""
            rows = range(i, min(len(self.table), i + self.chunk_rows))
            
            logger.info(f"Inserting values for rows {rows.start}-{rows.stop} of {len(self.table)}.")
            
            chunked_vals = self._data2SQLValue(rows)

            for vals in chunked_vals:
                stringified_chunk += f"{vals}, "

            stringified_chunk = stringified_chunk[:-2] # remove trailing ", "

            SQL_statement = f"INSERT INTO {self.dbctxt.sql_table} VALUES {stringified_chunk};"

            # connect to db & insert
            with psycopg.connect(host=self.dbctxt.POSTGRES_HOST, user=self.dbctxt.POSTGRES_USER, port=self.dbctxt.POSTGRES_PORT, password=self.dbctxt.POSTGRES_PASSWORD, dbname=self.dbctxt.POSTGRES_DB) as conn:
                with conn.cursor() as cur:
                    try:
                        cur.execute(SQL_statement)
                        conn.commit()
                    except Exception as e:
                        raise e
            logger.info("done.")

        q3c_index_table(self.dbctxt)


class TwoMASSConfig(CatalogConfig):
    relational_schema = """CREATE TABLE twomass_psc (
    ra double precision,
    decl double precision,
    err_maj real,
    err_min real,
    err_ang smallint,
    designation character(17),
    j_m real,
    j_cmsig real,
    j_msigcom real,
    j_snr real,
    h_m real,
    h_cmsig real,
    h_msigcom real,
    h_snr real,
    k_m real,
    k_cmsig real,
    k_msigcom real,
    k_snr real,
    ph_qual character(3),
    rd_flg character(3),
    bl_flg character(3),
    cc_flg character(3),
    ndet character(6),
    prox real,
    pxpa smallint,
    pxcntr integer,
    gal_contam smallint,
    mp_flg smallint,
    pts_key integer,
    hemis character(1),
    date date,
    scan smallint,
    glon real,
    glat real,
    x_scan real,
    jdate double precision,
    j_psfchi real,
    h_psfchi real,
    k_psfchi real,
    j_m_stdap real,
    j_msig_stdap real,
    h_m_stdap real,
    h_msig_stdap real,
    k_m_stdap real,
    k_msig_stdap real,
    dist_edge_ns integer,
    dist_edge_ew integer,
    dist_edge_flg character(2),
    dup_src smallint,
    use_src smallint,
    a character(1),
    dist_opt real,
    phi_opt smallint,
    b_m_opt real,
    vr_m_opt real,
    nopt_mchs smallint,
    ext_key integer,
    scan_key integer,
    coadd_key integer,
    coadd smallint
) WITHOUT OIDS;
"""
    def __init__(self, path: str):
        pass

