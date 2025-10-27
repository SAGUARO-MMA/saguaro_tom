import logging

import psycopg

logger = logging.getLogger(__name__)

class DBctxt():
    def __init__(self, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, sql_table):
        self.POSTGRES_HOST = POSTGRES_HOST
        self.POSTGRES_PORT = POSTGRES_PORT
        self.POSTGRES_USER = POSTGRES_USER
        self.POSTGRES_PASSWORD = POSTGRES_PASSWORD
        self.POSTGRES_DB = POSTGRES_DB
        self.sql_table = sql_table

def execute_statement(dbctxt: DBctxt, SQL_statement: str):
    logger.info("Executing SQL statement")
    logger.debug(SQL_statement)
    with psycopg.connect(host=dbctxt.POSTGRES_HOST, port=dbctxt.POSTGRES_PORT, dbname=dbctxt.POSTGRES_DB, user=dbctxt.POSTGRES_USER, password=dbctxt.POSTGRES_PASSWORD) as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(SQL_statement)
                conn.commit()
            except Exception as e: raise
            finally:
                logger.info("executed SQL statement.")

def q3c_index_table(dbctxt: DBctxt):
    SQL_statements = [f"CREATE INDEX ON {dbctxt.sql_table} (q3c_ang2ipix(ra, dec));", \
                      f"CLUSTER {dbctxt.sql_table}_q3c_ang2ipix_idx ON {dbctxt.sql_table};"] # q3c docs recommend to "cluster" as well
    
    execute_statement(dbctxt, SQL_statements[0])
    execute_statement(dbctxt, SQL_statements[1])

