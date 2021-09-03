import os
import sqlite3
import plistlib
import biplist
import inspect
import ccl_bplist
import nska_deserialize as nd
import argparse

'''
Roadmap:
Identify/skip "problem" plist files
Identify/hide deserialized "unhashable" error
Shorten filepath information for database (?)
Allow key/value keyword filtering (?)
Option to export binary blob data as string or binary (?) affects search/filter str(val)
'''

'''
Change Log
alpha 0.1 : Initial GitHub release
'''

'''
Notes
'''


class ParsePlistData:

    def __init__(self):
        self.conn_new = None
        self.cursor_new = None
        self.new_row = 0

        # used to display warning that -- unhashable type: 'NSKeyedArchiverDictionary' -- error may be displayed
        self.deserialize_error_count = 0

    def create_db(self, database_name):

        if os.path.isfile(database_name):
            try:
                os.remove(database_name)
            except Exception as e:
                print(f"Error removing previous database: {e}")
                exit(-1)

        self.conn_new = sqlite3.connect(database_name)
        self.conn_new.execute('pragma journal_mode=wal')
        self.cursor_new = self.conn_new.cursor()

        self.cursor_new.execute('''CREATE TABLE PROCESSED_FILES (
                                    id INTEGER PRIMARY KEY, file TEXT)''')
        self.cursor_new.execute('''CREATE TABLE PLIST_DATA (id INTEGER PRIMARY KEY,
                                    pf_id INT, 
                                    key_path TEXT, 
                                    key TEXT, 
                                    value BLOB,
                                    FOREIGN KEY (pf_id) REFERENCES PLIST_FILES (id))''')
        self.cursor_new.execute('''CREATE TABLE ERRORS (
                                    id INTEGER PRIMARY KEY, 
                                    pf_id INT, 
                                    processing_step TEXT, 
                                    error TEXT,
                                    FOREIGN KEY (pf_id) REFERENCES PLIST_FILES (id))''')
        self.cursor_new.execute('''CREATE VIEW ERRORS_VIEW AS SELECT
                                    file, processing_step, error FROM ERRORS INNER JOIN
                                    PROCESSED_FILES ON PROCESSED_FILES.id = ERRORS.pf_id''')
        self.cursor_new.execute('''CREATE VIEW PLIST_DATA_VIEW AS SELECT 
                                    file, key_path, key, value FROM PLIST_DATA INNER JOIN 
                                    PROCESSED_FILES ON PROCESSED_FILES.id = PLIST_DATA.pf_id''')

    def plistlib_load(self, load_file):

        with open(load_file, 'rb') as f:
            try:
                plist_data = plistlib.load(f)
                return plist_data
            except Exception as e:
                function_name = inspect.currentframe().f_code.co_name
                error_data = (self.new_row, function_name, str(e))
                self.update_db_error(error_data)
                return None

    def ccl_bplist_load(self, load_file):

        with open(load_file, "rb") as f:
            try:
                plist_data = ccl_bplist.load(f)
                return plist_data
            except Exception as e:
                function_name = inspect.currentframe().f_code.co_name
                error_data = (self.new_row, function_name, str(e))
                self.update_db_error(error_data)
                return None

    def biplist_load(self, load_file):

        with open(load_file, "rb") as f:
            try:
                plist_data = biplist.readPlist(f)
                return plist_data
            except Exception as e:
                function_name = inspect.currentframe().f_code.co_name
                error_data = (self.new_row, function_name, str(e))
                self.update_db_error(error_data)
                return None

    def ns_deserialize_plist(self, load_file):

        if self.deserialize_error_count == 0:
            self.deserialize_error_count = 1

        with open(load_file, 'rb') as f:
            # the below line is for testing purposes to identify problem plist files
            # print(load_file)
            try:
                deserialized_plist = nd.deserialize_plist(f)
            except Exception as e:
                function_name = inspect.currentframe().f_code.co_name
                error_data = (self.new_row, function_name, str(e))
                self.update_db_error(error_data)
                deserialized_plist = None

        if isinstance(deserialized_plist, dict):
            return deserialized_plist
        elif isinstance(deserialized_plist, list):
            error_data = (self.new_row, "ns_deserialize_plist",
                          "DESERIALIZE ERROR: May not have deserialized completely")
            self.update_db_error(error_data)
            return deserialized_plist
        else:
            return None

    def update_db_error(self, update_data):

        self.cursor_new.execute('''INSERT INTO ERRORS (pf_id, processing_step, error)
                                    VALUES (?, ?, ?)''', update_data)

    def update_db_data(self, update_data):

        self.cursor_new.execute('''INSERT INTO PLIST_DATA (pf_id, key_path, key, value)
                                            VALUES (?, ?, ?, ?)''', update_data)

    def update_db_files(self, file_name):

        self.cursor_new.execute('''INSERT INTO PROCESSED_FILES (file) VALUES (?)''', (file_name,))
        self.new_row = self.cursor_new.lastrowid

    def commit_db(self):

        self.conn_new.commit()
        if self.deserialize_error_count != 0:
            print(f"\nThe -- unhashable type: 'NSKeyedArchiverDictionary' -- message occurs sometimes when an "
                  f"NSKeyedArchiver plist is deserialized.\nSee the error table of the database to identify "
                  f"potentially affected files.")

    def processing_method(self, input_type, input_item):

        if input_type.lower() == "file":
            process_item = input_item
            self.processing_steps(process_item)
        elif input_type.lower() == "folder":
            for root, dirs, files in os.walk(input_item):
                for name in files:
                    process_item = os.path.join(root, name)
                    # the below line is for testing purposes to identify problem plist files
                    # print(process_item)
                    if process_item[1] == ':':
                        process_item = '\\\\?\\' + process_item.replace('/', '\\')
                    self.processing_steps(process_item)

    def processing_steps(self, processing_item):

        self.update_db_files(processing_item)

        processed_data = self.plistlib_load(processing_item)
        if processed_data is None:
            # processed_data = self.ccl_bplist_load(processing_item)
            processed_data = self.biplist_load(processing_item)
        if processed_data is None:
            processed_data = self.ccl_bplist_load(processing_item)
        if isinstance(processed_data, dict) and '$archiver' in processed_data.keys():
            processed_data = self.ns_deserialize_plist(processing_item)
        if processed_data is not None:
            self.recursive_dict_read(processing_item, processed_data)
        if processed_data is None:
            function_name = inspect.currentframe().f_code.co_name
            error_data = (self.new_row, function_name, "LOAD ERROR: Unable to load plist data")
            self.update_db_error(error_data)

    def recursive_dict_read(self, read_item, data, val="", parent_keys=""):

        if isinstance(data, dict):
            for key, value in data.items():
                self.recursive_dict_read(read_item, key, value)
        # attempt parsing NSKeyedArchiver deserialize results when a list is returned instead of a dict
        elif isinstance(data, list):
            if len(data) != 0:
                for i in data:
                    self.recursive_dict_read(read_item, i, "", parent_keys)
        elif isinstance(val, dict):
            if len(val) == 0:
                self.recursive_dict_read(read_item, data, "", parent_keys)
            for k, v in val.items():
                self.recursive_dict_read(read_item, k, v, parent_keys + f"{str(data)}\\")
        elif isinstance(val, list):
            if len(val) == 0:
                self.recursive_dict_read(read_item, data, "", parent_keys)
            for i in val:
                self.recursive_dict_read(read_item, data, i, parent_keys)
        else:
            # replace 0/1 for bool with True/False
            if type(val) == bool:
                val = str(bool(val))
            # remove/add the str(#) around val to export blob as blob/string
            parsed_data = (self.new_row, parent_keys, str(data), val)
            self.update_db_data(parsed_data)


if __name__ == '__main__':

    script = "plist_data_parser"
    version = "alpha0.1 (2021)"
    email = "pug4n6@gmail.com"
    github = "https://github.com/pug4n6"

    data_type = None

    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter,
                                     description=f"Plist Data Parser version {version}\n{github} | {email}"
                                                 f"\n\nReads XML and binary plist files, attempts to "
                                                 f"deserialize NSKeyedArchiver plists, and parses key/value "
                                                 f"combinations into a SQLite database."
                                                 f"\nNOTE: Boolean values replaced with True/False")
    parser.add_argument("-i", dest="input_data", required=True, action="store",
                        help="Input file or folder (required)")
    parser.add_argument("-o", dest="output_db", required=True, action="store",
                        help="Output database filename (required)")

    args = parser.parse_args()

    input_data = f"{args.input_data}"
    output_database = f"{args.output_db}"

    if os.path.isfile(input_data):
        data_type = "file"
    elif os.path.isdir(input_data):
        data_type = "folder"
    else:
        print("ERROR: Input file/folder could not be found.")
        exit(-1)

    data_parser = ParsePlistData()
    data_parser.create_db(output_database)
    data_parser.processing_method(data_type, input_data)
    data_parser.commit_db()

    print(f"\nPlist data parsing complete.\nInput data: {input_data}\nOutput database: {output_database}")
